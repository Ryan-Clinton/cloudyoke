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
    channels = {0: 1, 2: 3, 3: 1, 6: 4}[colour]
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


class WorldTest(unittest.TestCase):
    def test_each_place_gets_the_satellite_most_nearly_overhead(self):
        self.assertEqual(satellite.choose(55.07, -6.51), "meteosat")
        self.assertEqual(satellite.choose(39.74, -104.99), "goes-east")
        self.assertEqual(satellite.choose(21.3, -157.8), "goes-west")
        self.assertEqual(satellite.choose(-33.87, 151.21), "himawari")
        self.assertIsNone(satellite.choose(64.1, -21.9), "Reykjavik is too slanted a view for any of them")
        self.assertIsNone(satellite.choose(78.2, 15.6), "Svalbard")

    def test_boxes_stay_on_the_map(self):
        self.assertEqual(satellite.box(-17.7, 178.5)[1:4:2], (172.6, 180))

    def test_overcast_box_no_longer_reads_clear(self):
        """The whole box under cloud: its warmest tenth is cloud too, so the site's own clear history decides."""
        t0 = datetime(2026, 11, 1, 22, 0, tzinfo=timezone.utc)
        history = [(t0 + timedelta(days=d, minutes=m), {"here": 60.0 + m / 10, "satellite": "meteosat"})
                   for d in range(7) for m in (-60, -30, 0, 30, 60)]
        when = datetime(2026, 11, 8, 21, 50, tzinfo=timezone.utc)
        own = satellite.own_clear(history, when, "meteosat")
        self.assertIsNotNone(own)
        with mock.patch.object(satellite, "measure", return_value=(110.0, 105.0)):
            row = satellite.look("meteosat", 55.075, -6.525, when, history)
        self.assertEqual(row["verdict"], "cloud", "against the box alone (margin 5) it would say probably clear")
        with mock.patch.object(satellite, "measure", return_value=(110.0, 105.0)):
            self.assertEqual(satellite.look("meteosat", 55.075, -6.525, when, history[:5])["verdict"], "probably clear",
                             "too little history: the box alone, as before")

    def test_own_history_ignores_other_hours_and_satellites(self):
        when = datetime(2026, 11, 8, 22, 0, tzinfo=timezone.utc)
        noon = [(when - timedelta(days=d, hours=10), {"here": 1.0, "satellite": "meteosat"}) for d in range(1, 7) for _ in range(5)]
        other = [(when - timedelta(days=d), {"here": 1.0, "satellite": "goes-east"}) for d in range(1, 7) for _ in range(5)]
        self.assertIsNone(satellite.own_clear(noon + other, when, "meteosat"))

    def test_gibs_colours_read_as_celsius_with_blends_taken_to_the_nearest(self):
        colours = {(255, 255, 255): -90.0, (0, 0, 0): 30.0, (128, 128, 128): -5.0}
        data = png([[255, 255, 255, 255, 0, 0, 0, 255, 126, 129, 127, 255, 9, 9, 9, 0]], colour=6)
        self.assertEqual(satellite.png_celsius(data, colours)[2], [[-90.0, 30.0, -5.0, None]])


def fake_look(sat, lat, lon, when, history=()):
    return {"obs_time": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "satellite": sat, "units": "levels", "here": 80.0,
            "clear": 50.0, "margin": 30.0, "verdict": "cloud"}


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
        look = lambda sat, lat, lon, when, history=(): seen_at.append((lat, lon)) or fake_look(sat, lat, lon, when)
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
