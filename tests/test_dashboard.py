"""Tests for the reference-source dashboard."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import dashboard  # noqa: E402
import registry  # noqa: E402

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

    def test_each_site_gets_the_sources_near_it_and_stale_ones_are_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            registry.add_site(d, "home", "Ballymoney, County Antrim", 55.0712, -6.5143, public_cell=0.05)
            registry.add_site(d, "far", "Brecon, Wales", 51.95, -3.39)
            registry.note_references(d, {
                "EGAA": {"kind": "metar", "name": "Belfast International Airport", "lat": 54.654, "lon": -6.225},
                "EGPK": {"kind": "metar", "name": "Prestwick Airport", "lat": 55.509, "lon": -4.587},
                "MET-17": {"kind": "ceilometer", "name": "Malin Head", "lat": 55.3719, "lon": -7.3392},
                "EGFF": {"kind": "metar", "name": "Cardiff Airport", "lat": 51.397, "lon": -3.343}})
            write(d, "EGAA", "2026-11-10", [{"obs_time": "2026-11-10T00:20:00Z", "raw": "METAR EGAA 100020Z AUTO NCD",
                                             "cover": "NCD", "layers": []}])
            write(d, "MET-17", "2026-11-09", [{"obs_time": "2026-11-09T18:00:00Z", "layers": [{"base_ft": 22900, "oktas": 7, "vertical_visibility": False}]}])
            status = {s["site"]: s for s in dashboard.build(d, Path(d) / "www", NOW)}
            home = {s["source"]: s for s in status["home"]["sources"]}
            self.assertEqual(set(home), {"EGAA", "EGPK", "MET-17"}, "Cardiff is 400 km away, not Ballymoney's")
            self.assertEqual([s["source"] for s in status["far"]["sources"]], ["EGFF"])
            self.assertFalse(home["EGAA"]["stale"])
            self.assertTrue(home["MET-17"]["stale"], "a ceilometer silent for over 3 hours is stale")
            self.assertIsNone(home["EGPK"]["latest"])
            self.assertTrue(home["EGPK"]["stale"], "a source with nothing at all is stale, never quietly absent")
            self.assertEqual(home["EGAA"]["distance_km"] % 5, 0, "distances are rounded to 5 km")
            page = (Path(d) / "www" / "sites" / "home" / "index.html").read_text()
            self.assertIn("observations, not predictions", page)
            self.assertIn("Contains Met Éireann data", page)
            overview = (Path(d) / "www" / "index.html").read_text()
            self.assertIn('href="sites/far/"', overview)
            public = overview + page + (Path(d) / "www" / "status.json").read_text()
            for leak in ("55.07", "-6.51", "51.95", "-3.39"):
                self.assertNotIn(leak, public, "a site's position never reaches a page")

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

    def test_distance(self):
        km, way = registry.distance(55.07, -6.51, 55.3719, -7.3392)
        self.assertEqual((round(km), way), (62, "NW"))


if __name__ == "__main__":
    unittest.main()
