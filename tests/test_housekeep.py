"""Tests for the daily housekeeping: python -m unittest discover -s tests"""
import bz2
import json
import lzma
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import housekeep  # noqa: E402
import metar  # noqa: E402

TODAY = date(2026, 11, 22)


def day(age):
    return TODAY - timedelta(days=age)


def row(source, age, n=0):
    key = "station" if source.startswith("MET-") else "icao"
    return json.dumps({key: source, "obs_time": f"{day(age)}T00:{n:02d}:00Z", "raw": f"{source} {n}"}).encode() + b"\n"


def put(root, folder, age, body=None):
    source = folder.split("/")[-1]
    path = Path(root) / folder / f"{day(age)}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(row(source, age) if body is None else body)
    return path


def bundle_rows(root, kind, age):
    path = housekeep.bundle_path(root, kind, day(age))
    codec = bz2 if kind == "airports" else lzma
    return [line for line in codec.decompress(path.read_bytes()).split(b"\n") if line]


class HousekeepTest(unittest.TestCase):
    def test_a_days_airports_become_one_bundle_after_7_days_keeping_every_row(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0), put(d, "reference/KDCA", 0)
            keep = put(d, "reference/EIDW", 7)
            a = put(d, "reference/EIDW", 8, row("EIDW", 8, 2) + row("EIDW", 8, 1))
            b = put(d, "reference/KDCA", 8)
            housekeep.run(d, TODAY, True)
            self.assertTrue(keep.exists())
            self.assertFalse(a.exists() or b.exists())
            self.assertEqual(bundle_rows(d, "airports", 8),
                             [row("EIDW", 8, 1).strip(), row("EIDW", 8, 2).strip(), row("KDCA", 8).strip()])

    def test_ceilometers_get_their_own_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/MET-1", 0)
            old = put(d, "reference/MET-1", 9)
            housekeep.run(d, TODAY, True)
            self.assertFalse(old.exists())
            self.assertEqual(bundle_rows(d, "ceilometers", 9), [row("MET-1", 9).strip()])

    def test_a_later_backfill_merges_without_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0)
            put(d, "reference/EIDW", 9)
            housekeep.run(d, TODAY, True)
            put(d, "reference/EIDW", 9, row("EIDW", 9) + row("EIDW", 9, 5))
            housekeep.run(d, TODAY, True)
            self.assertEqual(len(bundle_rows(d, "airports", 9)), 2)

    def test_satellite_files_are_not_bundled(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "satellite/ballymoney", 0)
            s = put(d, "satellite/ballymoney", 200)
            housekeep.run(d, TODAY, True)
            self.assertTrue(s.exists())

    def test_deleted_after_400_days_including_bundles(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0), put(d, "satellite/ballymoney", 0)
            sat, plain = put(d, "satellite/ballymoney", 401), put(d, "reference/EIDW", 401)
            kept = housekeep.bundle_path(d, "airports", day(400))
            gone = housekeep.bundle_path(d, "airports", day(401))
            kept.parent.mkdir(parents=True)
            kept.write_bytes(bz2.compress(b"x\n")), gone.write_bytes(bz2.compress(b"x\n"))
            housekeep.run(d, TODAY, True)
            self.assertTrue(kept.exists())
            self.assertFalse(sat.exists() or plain.exists() or gone.exists())

    def test_a_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/MET-1", 0)
            a, b = put(d, "reference/MET-1", 20), put(d, "reference/MET-1", 500)
            got = housekeep.run(d, TODAY, False)
            self.assertEqual((got[0], got[2]), (1, 1))
            self.assertTrue(a.exists() and b.exists())
            self.assertFalse((Path(d) / "archive").exists())

    def test_station_readings_and_other_files_are_never_touched(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0)
            unit, other = put(d, "cy-0001", 900), Path(d) / "reference" / "EIDW" / "notes.jsonl"
            other.write_text("mine")
            odd = put(d, "reference/not-a-source", 500), put(d, "reference/not-a-source", 20)
            housekeep.run(d, TODAY, True)
            self.assertTrue(unit.exists() and other.exists() and odd[1].exists())

    def test_a_quiet_sources_newest_file_stays_whatever_its_age(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0)
            quiet = put(d, "reference/MET-9", 500)
            housekeep.run(d, TODAY, True)
            self.assertTrue(quiet.exists())

    def test_a_wrong_clock_does_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 40)
            old = put(d, "reference/EIDW", 500)
            with self.assertRaises(ValueError):
                housekeep.run(d, TODAY, True)
            self.assertTrue(old.exists())

    def test_a_damaged_bundle_stops_that_day_and_keeps_its_files(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0)
            path = put(d, "reference/EIDW", 20)
            target = housekeep.bundle_path(d, "airports", day(20))
            target.parent.mkdir(parents=True)
            target.write_bytes(b"not a bundle")
            problems = housekeep.run(d, TODAY, True)[4]
            self.assertEqual(len(problems), 1)
            self.assertTrue(path.exists())

    def test_metar_load_reads_bundled_days_beside_plain_files(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0), put(d, "reference/KDCA", 0)
            put(d, "reference/EIDW", 9), put(d, "reference/KDCA", 9)
            housekeep.run(d, TODAY, True)
            put(d, "reference/EIDW", 9)                 # the same report again, from a backfill
            start = datetime(2026, 11, 1, tzinfo=timezone.utc)
            got = metar.load(d, "EIDW", start, start + timedelta(days=30))
            self.assertEqual([r[1]["obs_time"][:10] for r in got], [str(day(9)), str(day(0))])


if __name__ == "__main__":
    unittest.main()
