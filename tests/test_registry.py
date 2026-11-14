"""Tests for the registry, per-site reference finding and the night centred on a site's solar midnight."""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import met_eireann  # noqa: E402
import metar  # noqa: E402
import night_graph  # noqa: E402
import registry  # noqa: E402


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        registry.add_site(self.root, "home", "Ballymoney, County Antrim", 55.0712, -6.5143, population=9625)

    def tearDown(self):
        self.dir.cleanup()

    def test_a_key_is_shown_once_and_kept_only_as_a_hash(self):
        unit, key = registry.register(self.root, "home", ["sensor=BAA"])
        self.assertEqual(unit, "cy-0001")
        text = (Path(self.root) / "stations.json").read_text()
        self.assertNotIn(key, text)
        self.assertEqual(oct((Path(self.root) / "stations.json").stat().st_mode & 0o777), "0o600")
        self.assertEqual(registry.Keys(self.root).unit_for(key), "cy-0001")
        self.assertEqual(registry.register(self.root, "home")[0], "cy-0002")

    def test_keys_are_read_live_and_revoking_works_at_once(self):
        keys = registry.Keys(self.root)
        self.assertIsNone(keys.unit_for("anything"), "no stations file yet: nobody is known")
        unit, key = registry.register(self.root, "home")
        self.assertEqual(keys.unit_for(key), unit, "a new station is known without a restart")
        registry.revoke(self.root, unit)
        self.assertIsNone(keys.unit_for(key))
        self.assertIsNone(keys.unit_for(""))

    def test_a_revocation_in_the_same_clock_tick_is_still_seen(self):
        import os
        keys = registry.Keys(self.root)
        unit, key = registry.register(self.root, "home")
        path = Path(self.root) / "stations.json"
        before = path.stat().st_mtime_ns
        self.assertEqual(keys.unit_for(key), unit)
        registry.revoke(self.root, unit)
        os.utime(path, ns=(before, before))           # the same mtime as before: only the inode and size differ
        self.assertIsNone(keys.unit_for(key))

    def test_sites_are_snapped_and_given_their_public_cell(self):
        registry.add_site(self.root, "village", "Somewhere small", 54.1234, -7.4321)
        s = registry.sites(self.root)
        self.assertEqual((s["home"]["lat"], s["home"]["lon"]), (55.075, -6.525))
        self.assertEqual(s["home"]["public"], (55.075, -6.525))
        self.assertEqual(s["village"]["public"], (54.1, -7.5), "0.2° unless a smaller cell is safe")
        registry.add_site(self.root, "v2", "Somewhere small", 54.1249, -7.4301)
        registry.add_site(self.root, "v3", "Somewhere small", 54.1201, -7.4349)
        self.assertEqual(registry.sites(self.root)["village"]["public_cell"], 0.05, "three sites in one 0.05° cell")
        with self.assertRaises(ValueError):
            registry.add_site(self.root, "home", "again", 1, 1)
        with self.assertRaises(ValueError):
            registry.add_site(self.root, "Bad Id", "x", 1, 1)

    def test_setups_are_dated_rows(self):
        unit, _ = registry.register(self.root, "home", ["hood=none"])
        registry.new_setup(self.root, unit, ["hood=printed"])
        setups = registry.stations(self.root)[unit]["setups"]
        self.assertEqual([s["hood"] for s in setups], ["none", "printed"])
        self.assertEqual(registry.site_of(self.root, unit)["area"], "Ballymoney, County Antrim")

    def test_airports_are_found_by_distance_from_each_site(self):
        answer = [{"icaoId": "EGAA", "name": "Belfast/Aldergrove Intl, NI, GB", "lat": 54.654, "lon": -6.225, "obsTime": 1},
                  {"icaoId": "EGNS", "name": "Isle of Man", "lat": 54.083, "lon": -4.623, "obsTime": 1},
                  {"icaoId": "EGPK", "name": "Prestwick", "lat": 55.509, "lon": -4.587, "obsTime": 1},
                  {"icaoId": "EIKN", "name": "Knock", "lat": 53.91, "lon": -8.818, "obsTime": 1}]
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = json.dumps(answer).encode()
        with mock.patch.object(metar.urllib.request, "urlopen", return_value=resp):
            near = metar.fetch_near(55.075, -6.525, 6)
        self.assertEqual([m["icaoId"] for m in near], ["EGAA", "EGPK"],
                         "the Isle of Man (160 km) and the box's corner (Knock, 190 km) are left out")
        metar.note_positions(self.root, near)
        self.assertEqual(registry.references(self.root)["EGAA"]["name"], "Belfast/Aldergrove Intl")

    def test_ceilometers_near_any_site(self):
        places = {17: (55.37, -7.34), 9: (51.48, -9.43)}
        self.assertEqual(met_eireann.near_sites(self.root, places), [17])


class NightTest(unittest.TestCase):
    def test_a_night_is_centred_on_solar_midnight(self):
        self.assertEqual(night_graph.night_start(date(2026, 11, 20), 0), datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(night_graph.night_start(date(2026, 11, 20), -6.525), datetime(2026, 11, 20, 12, 26, tzinfo=timezone.utc))
        self.assertEqual(night_graph.night_start(date(2026, 11, 20), 151.2), datetime(2026, 11, 20, 1, 55, tzinfo=timezone.utc),
                         "Sydney's night starts at its own noon, 01:55 UTC, not halfway through")
        self.assertEqual(night_graph.night_start(date(2026, 11, 20), -118.2), datetime(2026, 11, 20, 19, 52, tzinfo=timezone.utc))

    def test_load_uses_the_station_site_longitude(self):
        with tempfile.TemporaryDirectory() as d:
            registry.add_site(d, "sydney", "Sydney, Australia", -33.87, 151.21)
            unit, _ = registry.register(d, "sydney")
            folder = Path(d) / unit
            folder.mkdir()
            rows = [{"t": "2026-11-20T14:00:00Z", "t_ok": True, "readings": {}}, {"t": "2026-11-21T01:00:00Z", "t_ok": True, "readings": {}},
                    {"t": "2026-11-21T03:00:00Z", "t_ok": True, "readings": {}}]
            for r in rows:
                with (folder / f"{r['t'][:10]}.jsonl").open("a") as f:
                    f.write(json.dumps(r) + "\n")
            start, end, got = night_graph.load(d, unit, date(2026, 11, 20))
            self.assertEqual(start.hour, 1)
            self.assertEqual(len(got), 2, "03:00 UTC on the 21st is the next afternoon in Sydney")


if __name__ == "__main__":
    unittest.main()
