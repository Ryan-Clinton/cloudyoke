"""Tests for the reference-source dashboard."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import dashboard  # noqa: E402

NOW = datetime(2026, 11, 10, 0, 40, tzinfo=timezone.utc)


def write(root, key, day, rows):
    path = Path(root) / "reference" / key / f"{day}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


class DashboardTest(unittest.TestCase):
    def test_latest_is_the_newest_time_not_the_last_line(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, "EGAE", "2026-11-09", [{"obs_time": "2026-11-09T23:20:00Z", "raw": "late"},
                                            {"obs_time": "2026-11-09T17:50:00Z", "raw": "early, appended by a backfill"}])
            t, r = dashboard.latest(d, "EGAE")
            self.assertEqual(r["raw"], "late")

    def test_status_flags_stale_and_missing_sources(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, "EGAA", "2026-11-10", [{"obs_time": "2026-11-10T00:20:00Z", "raw": "METAR EGAA 100020Z AUTO NCD",
                                             "cover": "NCD", "layers": []}])
            write(d, "MET-17", "2026-11-09", [{"obs_time": "2026-11-09T18:00:00Z", "layers": [{"base_ft": 22900, "oktas": 7, "vertical_visibility": False}]}])
            status = {s["source"]: s for s in dashboard.build(d, Path(d) / "www", NOW)}
            self.assertFalse(status["EGAA"]["stale"])
            self.assertTrue(status["MET-17"]["stale"], "a ceilometer silent for over 3 hours is stale")
            self.assertIsNone(status["EGPK"]["latest"])
            self.assertTrue(status["EGPK"]["stale"], "a source with nothing at all is stale, never quietly absent")
            page = (Path(d) / "www" / "index.html").read_text()
            self.assertIn("observations, not predictions", page)
            self.assertIn("Contains Met Éireann data", page)
            self.assertTrue(json.loads((Path(d) / "www" / "status.json").read_text())["sources"])

    def test_high_layer_and_codes(self):
        self.assertEqual(dashboard.oktas("ceilometer", {"layers": [{"base_ft": 22900, "oktas": 7}]}), (7, True))
        self.assertEqual(dashboard.oktas("ceilometer", {"layers": [{"base_ft": 200, "oktas": 9, "vertical_visibility": True}]}), (8, False))
        self.assertEqual(dashboard.oktas("metar", {"cover": "NCD", "layers": []}), (0, False))
        self.assertEqual(dashboard.describe("ceilometer", {"layers": []}), "no cloud base detected straight overhead")

    def test_bins_keep_the_most_cloud_and_the_high_mark(self):
        from datetime import timedelta
        t0 = datetime(2026, 11, 9, 23, 0, tzinfo=timezone.utc)
        rows = [(t0 + timedelta(seconds=15 * i), {"layers": [{"base_ft": 22900 if i == 3 else 4000, "oktas": 2 + (i == 5) * 5}]})
                for i in range(40)]                                      # 10 minutes of 15-second readings
        b = dashboard.bins(rows)
        self.assertEqual(len(b), 2)
        self.assertEqual(dashboard.oktas("ceilometer", b[0][1]), (7, True))
        self.assertEqual(dashboard.oktas("ceilometer", b[1][1]), (2, False))

    def test_place(self):
        self.assertEqual(dashboard.place(55.3719, -7.3392), (62, "NW"))


if __name__ == "__main__":
    unittest.main()
