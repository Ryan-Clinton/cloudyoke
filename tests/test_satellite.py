"""Tests for the satellite judge, the ground reports' scoring and the joined sites' page."""
import json
import struct
import sys
import tempfile
import unittest
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import satellite  # noqa: E402
import seen  # noqa: E402
import dashboard  # noqa: E402

NOW = datetime(2026, 11, 14, 22, 5, tzinfo=timezone.utc)


def png(rows, colour=0, palette=None, filt=0):
    """A small 8-bit PNG; every row uses filter `filt` (only 0 and 1 are encoded here)."""
    channels = {0: 1, 2: 3, 3: 1}[colour]
    raw = b""
    for row in rows:
        flat = bytes(row)
        if filt == 1:
            flat = bytes((flat[i] - (flat[i - channels] if i >= channels else 0)) & 255 for i in range(len(flat)))
        raw += bytes([filt]) + flat
    chunk = lambda kind, body: struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    w = len(rows[0]) // channels
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, len(rows), 8, colour, 0, 0, 0))
    if palette:
        out += chunk(b"PLTE", b"".join(bytes(p) for p in palette))
    return out + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class PngTest(unittest.TestCase):
    def test_grey_with_sub_filter(self):
        w, h, rows = satellite.png_grey(png([[10, 20, 30], [200, 100, 0]], filt=1))
        self.assertEqual((w, h, rows), (3, 2, [[10, 20, 30], [200, 100, 0]]))

    def test_palette_becomes_pillow_grey(self):
        palette = [(0, 0, 0), (255, 255, 255), (255, 0, 0)]
        _, _, rows = satellite.png_grey(png([[0, 1, 2]], colour=3, palette=palette))
        self.assertEqual(rows, [[0, 255, 76]], "Pillow's L for pure red is 76")

    def test_rgb(self):
        _, _, rows = satellite.png_grey(png([[0, 255, 0, 0, 0, 255]], colour=2))
        self.assertEqual(rows, [[150, 29]])

    def test_not_a_png_is_refused(self):
        with self.assertRaises(ValueError):
            satellite.png_grey(b"<html>error</html>")


class JudgeTest(unittest.TestCase):
    def test_cell_centre_hides_the_position(self):
        self.assertEqual(satellite.cell(55.0712, -6.5143), (55.075, -6.525))
        self.assertEqual(satellite.cell(55.0749, -6.5001), (55.075, -6.525), "anywhere in a cell gives its centre")

    def test_thresholds(self):
        self.assertEqual(satellite.verdict(25), "cloud")
        self.assertEqual(satellite.verdict(15), "thin or broken cloud")
        self.assertEqual(satellite.verdict(5), "probably clear")

    def test_site_at_centre_against_darkest_tenth(self):
        w, h = 40, 20
        rows = [[50] * w for _ in range(h)]
        for j in range(h // 2 - 4, h // 2 + 5):
            for i in range(w // 2 - 4, w // 2 + 5):
                rows[j][i] = 90
        here, clear = satellite.judge(w, h, rows)
        self.assertEqual((here, clear), (90, 50))


def fake_look(lat, lon, when):
    return {"obs_time": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "here": 80.0, "clear": 50.0, "margin": 30.0, "verdict": "cloud"}


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "sites.json").write_text(json.dumps(
            {"home": {"area": "Ballymoney, County Antrim", "lat": 55.0712, "lon": -6.5143, "as": "station"}}))

    def tearDown(self):
        self.dir.cleanup()

    def test_keeps_each_picture_once_and_judges_at_the_cell(self):
        seen_at = []
        look = lambda lat, lon, when: seen_at.append((lat, lon)) or fake_look(lat, lon, when)
        with mock.patch.object(satellite, "picture_time", return_value=NOW - timedelta(minutes=25)), \
                mock.patch.object(satellite, "look", side_effect=look):
            satellite.collect(self.root, hours=0.5, now=NOW)
            satellite.collect(self.root, hours=0.5, now=NOW)
        self.assertEqual(len(satellite.kept_times(self.root, "home")), 4, "newest and three before, once each")
        self.assertEqual(set(seen_at), {(55.075, -6.525)})

    def test_a_stopped_service_keeps_nothing(self):
        with mock.patch.object(satellite, "picture_time", return_value=NOW - timedelta(hours=2)):
            lines = satellite.collect(self.root, now=NOW)
        self.assertIn("stopped", lines[0])
        self.assertFalse((self.root / "satellite").exists())

    def test_scores_and_page(self):
        with mock.patch.object(satellite, "picture_time", return_value=NOW - timedelta(minutes=25)), \
                mock.patch.object(satellite, "look", side_effect=fake_look):
            satellite.collect(self.root, hours=1, now=NOW)
        seen.add(self.root, "home", "2026-11-14T21:00", "2026-11-14T21:30", "clear", "station")
        s = seen.score(self.root, "home")
        self.assertEqual((s["n"], s["agree"], s["false_cloud"]), (3, 0, 3))
        status = dashboard.build(self.root, self.root / "www", NOW)
        self.assertEqual(status[0]["satellite"]["verdict"], "cloud")
        page = (self.root / "www" / "sites" / "home" / "index.html").read_text()
        self.assertIn("Ballymoney, County Antrim", page)
        self.assertIn("agreed 0 of 3", page)
        for leak in ("55.07", "-6.51", "55.075", "-6.525"):
            self.assertNotIn(leak, page + (self.root / "www" / "status.json").read_text())

    def test_a_report_must_end_after_it_starts(self):
        with self.assertRaises(ValueError):
            seen.add(self.root, "home", "2026-11-14T22:00", "2026-11-14T21:00", "clear", "station")


if __name__ == "__main__":
    unittest.main()
