"""Tests for the minimum receiver and the night graph. Standard library only:

    python -m unittest discover -s tests
"""
import json
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import night_graph  # noqa: E402
import pretend_station  # noqa: E402
import receiver  # noqa: E402

KEY = "test-secret-0001"


class ReceiverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.server = receiver.serve("127.0.0.1:0", self.data, {"cy-0001": KEY, "cy-0002": "other-secret"})
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/cloudyoke/send"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def post(self, body, key=KEY, raw=None):
        data = raw if raw is not None else json.dumps(body).encode()
        req = urllib.request.Request(self.url, data=data, method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def stored(self, unit="cy-0001"):
        self.server.RequestHandlerClass.store.queue.join()
        return [json.loads(line) for p in sorted((self.data / unit).glob("*.jsonl")) for line in p.read_text().splitlines()]

    def reading(self, seq, **extra):
        r = next(pretend_station.night("cy-0001", date(2026, 11, 20)))
        r.update(seq=seq, **extra)
        return r

    def test_stores_one_and_a_batch(self):
        self.assertEqual(self.post(self.reading(1)), (200, {"ok": True, "stored": 1, "duplicates": 0}))
        self.assertEqual(self.post([self.reading(2), self.reading(3)])[1]["stored"], 2)
        rows = self.stored()
        self.assertEqual([r["seq"] for r in rows], [1, 2, 3])
        self.assertTrue(all("received" in r for r in rows))

    def test_resend_is_a_duplicate_not_a_second_copy(self):
        self.post(self.reading(1))
        self.assertEqual(self.post(self.reading(1))[1], {"ok": True, "stored": 0, "duplicates": 1})
        self.assertEqual(len(self.stored()), 1)

    def test_duplicates_survive_a_restart(self):
        self.post(self.reading(1))
        self.stored()
        day = self.reading(1)["t"][:10]
        fresh = receiver.Store(self.data)
        self.assertFalse(fresh.claim("cy-0001", day, 1, 1))
        self.assertTrue(fresh.claim("cy-0001", day, 1, 2))
        self.assertTrue(all(k[1] == day for k in fresh.seen), "only the reading's own day is loaded")

    def test_a_reading_from_the_future_is_refused(self):
        late = self.reading(1, t="2099-01-01T00:00:00Z")
        self.assertEqual(self.post(late)[0], 400)
        self.assertEqual(self.stored(), [])

    def test_wrong_or_missing_key(self):
        self.assertEqual(self.post(self.reading(1), key="nope")[0], 401)
        self.assertEqual(self.post(self.reading(1), key="")[0], 401)
        self.assertEqual(self.stored(), [])

    def test_another_stations_key_cant_send_for_this_one(self):
        self.assertEqual(self.post(self.reading(1), key="other-secret")[0], 400)
        self.assertEqual(self.stored(), [])

    def test_bad_reading_refuses_the_whole_send(self):
        bad = self.reading(2)
        del bad["readings"]["sky_c"]
        self.assertEqual(self.post([self.reading(1), bad])[0], 400)
        self.assertEqual(self.stored(), [])

    def test_not_json_and_wrong_path(self):
        self.assertEqual(self.post(None, raw=b"{not json")[0], 400)
        req = urllib.request.Request(self.url.replace("/send", "/other"), data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(e.exception.code, 404)

    def test_full_queue_asks_for_a_resend_and_forgets_the_claim(self):
        store = self.server.RequestHandlerClass.store
        original = store.queue
        store.queue = __import__("queue").Queue(1)
        store.queue.put({"placeholder": True})      # full, and nothing is draining this one
        try:
            self.assertEqual(self.post(self.reading(1))[0], 503)
            self.assertTrue(store.claim("cy-0001", self.reading(1)["t"][:10], 1, 1),
                            "a refused reading must be accepted when resent")
        finally:
            store.queue = original

    def test_nan_and_infinity_are_refused(self):
        for word in (b"NaN", b"Infinity", b"-Infinity"):
            body = json.dumps(self.reading(1)).replace('"sky_c": -', '"sky_c": X').encode()
            body = re.sub(rb'"sky_c": X[0-9.]+', b'"sky_c": ' + word, body)
            self.assertEqual(self.post(None, raw=body)[0], 400, word)
        self.assertEqual(self.stored(), [])

    def test_odd_strings_are_stored_safely(self):
        r = self.reading(1, fw="\ud800-lone-surrogate")
        body = json.dumps(r).encode()              # json escapes the lone surrogate as \\ud800
        self.assertEqual(self.post(None, raw=body)[0], 200)
        self.assertEqual(self.stored()[0]["fw"], "\ud800-lone-surrogate")

    def test_a_failed_write_is_reported_and_the_writer_lives(self):
        (self.data / "cy-0001").write_text("a file where the station's folder should be")
        status, answer = self.post(self.reading(1))
        self.assertEqual((status, answer["stored"]), (503, 0))
        (self.data / "cy-0001").unlink()
        self.assertEqual(self.post(self.reading(1))[1], {"ok": True, "stored": 1, "duplicates": 0})
        self.assertEqual(len(self.stored()), 1)

    def test_pretend_night_end_to_end_and_graph(self):
        readings = list(pretend_station.night("cy-0001", date(2026, 11, 20)))
        for i in range(0, len(readings), 60):
            self.assertEqual(self.post(readings[i:i + 60])[0], 200)
        self.assertEqual(self.post(readings[:60])[1]["duplicates"], 60)
        self.assertEqual(len(self.stored()), len(readings))
        start, end, rows = night_graph.load(self.data, "cy-0001", date(2026, 11, 20))
        self.assertEqual(len(rows), len(readings))
        svg = night_graph.draw("cy-0001", start, end, rows)
        self.assertTrue(svg.startswith("<svg") and svg.endswith("</svg>"))
        # The 30-minute power cut splits each line in two
        self.assertEqual(len(night_graph.series(rows, lambda r: r["readings"]["sky_c"])), 2)
        self.assertIn("10 flagged readings", svg)
        self.assertIn("MADE-UP DATA", svg)


class GraphTest(unittest.TestCase):
    def test_empty_night_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            start, end, rows = night_graph.load(d, "cy-0009", date(2026, 11, 20))
            self.assertIn("No readings this night", night_graph.draw("cy-0009", start, end, rows))

    def test_bridge_values_are_read_too(self):
        self.assertEqual(night_graph.value({"value": -20.5, "age_s": 3, "processing": "raw"}), -20.5)
        self.assertEqual(night_graph.value(-20.5), -20.5)
        self.assertIsNone(night_graph.value(None))

    def test_wild_values_cant_hang_or_stretch_the_graph(self):
        for bad in (float("nan"), float("inf"), True):
            self.assertIsNone(night_graph.value(bad))
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        rows = [(start + timedelta(hours=8), {"readings": {"sky_c": 1e300, "air_c": -1e300}, "flags": []})]
        svg = night_graph.draw("cy-0001", start, start + timedelta(days=1), rows)
        self.assertLessEqual(svg.count("°C</text>"), 21)


if __name__ == "__main__":
    unittest.main()
