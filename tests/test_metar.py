"""Tests for the METAR reference source and its graphs, using real report shapes from the Aviation Weather
Center's JSON API (no network needed):

    python -m unittest discover -s tests
"""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import metar  # noqa: E402
import metar_graph  # noqa: E402
import night_graph  # noqa: E402

# Real records for City of Derry, as the API returned them on 9 November 2026 (trimmed to the fields used)
CAVOK = {"icaoId": "EGAE", "obsTime": 1794266400, "reportTime": "2026-11-09T23:20:00.000Z", "temp": 3, "dewp": 3,
         "wdir": 40, "wspd": 3, "visib": "6+", "altim": 1014, "metarType": "METAR",
         "rawOb": "METAR EGAE 092320Z 04003KT 010V070 CAVOK 03/03 Q1014", "cover": "CAVOK", "clouds": []}
CLOUDY = {"icaoId": "EGAE", "obsTime": 1793103600, "visib": "6+", "metarType": "METAR",
          "rawOb": "METAR EGAE 271250Z 24022KT 9999 VCSH FEW025CB SCT041 12/07 Q0999", "cover": "SCT",
          "clouds": [{"cover": "FEW", "base": 2500}, {"cover": "SCT", "base": 4100}], "wxString": "VCSH"}
FOG = {"icaoId": "EGAE", "obsTime": 1794034200, "visib": 0.25, "metarType": "METAR",
       "rawOb": "METAR EGAE 070650Z 21003KT 0400 FG VV001 03/03 Q1018", "cover": "OVX", "clouds": [], "wxString": "FG"}


class DecodeTest(unittest.TestCase):
    def test_codes_are_kept_never_turned_into_clear(self):
        o = metar.decode(CAVOK)
        self.assertEqual(o["cover"], "CAVOK")
        self.assertEqual(o["layers"], [])
        self.assertNotIn("clear", str(o).lower().replace("cleared", ""))

    def test_ncd_is_kept_although_the_api_says_clr(self):
        # Belfast International's real report, 9 Nov 2026 23:20, with the API's cover field as it came
        egaa = {"icaoId": "EGAA", "obsTime": 1794266400, "visib": "6+", "cover": "CLR", "clouds": [],
                "rawOb": "METAR EGAA 092320Z AUTO 08004KT 9999 NCD 03/03 Q1014"}
        o = metar.decode(egaa)
        self.assertEqual((o["cover"], o["api_cover"], o["auto"]), ("NCD", "CLR", True))

    def test_real_observation_time_not_the_rounded_report_time(self):
        # obsTime is 23:20 here; the API's reportTime for the 22:50 report says 23:00, so obsTime is the one kept
        self.assertEqual(metar.decode(CAVOK)["obs_time"], "2026-11-09T23:20:00Z")

    def test_layers_visibility_and_fog(self):
        o = metar.decode(CLOUDY)
        self.assertEqual(o["layers"], [{"cover": "FEW", "base_ft": 2500}, {"cover": "SCT", "base_ft": 4100}])
        self.assertEqual((o["visibility_km"], o["visibility_or_more"]), (9.7, True))
        f = metar.decode(FOG)
        self.assertEqual((f["vertical_visibility_ft"], f["weather"], f["visibility_km"]), (100, "FG", 0.4))
        self.assertFalse(f["auto"])

    def test_visibility_text(self):
        self.assertEqual(metar.visibility_km("6+"), (9.7, True))
        self.assertEqual(metar.visibility_km(None), (None, False))
        self.assertEqual(metar.visibility_km("junk"), (None, False))


class StoreTest(unittest.TestCase):
    def test_kept_once_and_loaded_in_order(self):
        with tempfile.TemporaryDirectory() as d:
            obs = [metar.decode(m) for m in (CAVOK, CLOUDY, FOG)]
            self.assertEqual(metar.store(d, obs), 3)
            self.assertEqual(metar.store(d, obs), 0)
            corrected = dict(CAVOK, rawOb=CAVOK["rawOb"].replace("METAR EGAE", "METAR COR EGAE"))
            self.assertEqual(metar.store(d, [metar.decode(corrected)]), 1, "a correction is kept beside the original")
            rows = metar.load(d, "EGAE", datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 12, 1, tzinfo=timezone.utc))
            self.assertEqual([r["raw"][:20] for _, r in rows][:2], ["METAR EGAE 271250Z 2", "METAR EGAE 070650Z 2"])
            self.assertEqual(len(rows), 4)


class GraphTest(unittest.TestCase):
    def test_metar_graph_draws_and_labels_itself_a_reference(self):
        start = datetime(2026, 11, 7, tzinfo=timezone.utc)
        rows = [(datetime.fromisoformat(o["obs_time"].replace("Z", "+00:00")), o) for o in map(metar.decode, (FOG, CAVOK))]
        svg = metar_graph.draw("EGAE", start, start + timedelta(days=3), rows)
        self.assertIn("not a cloudyoke station", svg)
        self.assertIn("not the same as a clear sky", svg)
        self.assertTrue(svg.endswith("</svg>"))

    def test_night_graph_strip(self):
        start = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        rows = [(datetime.fromisoformat(o["obs_time"].replace("Z", "+00:00")), o) for o in map(metar.decode, (CAVOK,))]
        svg = night_graph.draw("cy-0001", start, start + timedelta(days=1), [], ("EGAE", rows))
        self.assertIn("EGAE airport reports (METAR), a reference, not a reading", svg)
        self.assertIn('fill="#ffffff"', svg)          # CAVOK shown white, labelled not the same as clear
        empty = night_graph.draw("cy-0001", start, start + timedelta(days=1), [], ("EGAE", []))
        self.assertIn("no reports from EGAE this night", empty)


if __name__ == "__main__":
    unittest.main()
