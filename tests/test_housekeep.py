"""Tests for the daily housekeeping: python -m unittest discover -s tests"""
import gzip
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import housekeep  # noqa: E402

TODAY = date(2026, 11, 22)


def put(root, folder, age, body=b'{"obs_time":"x"}\n', suffix=".jsonl"):
    path = Path(root) / folder / f"{TODAY - timedelta(days=age)}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(body) if suffix.endswith(".gz") else body)
    return path


class HousekeepTest(unittest.TestCase):
    def test_ceilometers_compress_after_14_days_and_keep_every_byte(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/MET-1", 0)
            keep, old = put(d, "reference/MET-1", 14), put(d, "reference/MET-1", 15, b"the readings\n" * 50)
            housekeep.run(d, TODAY, True)
            self.assertTrue(keep.exists())
            self.assertFalse(old.exists())
            self.assertEqual(gzip.decompress(old.with_name(old.name + ".gz").read_bytes()), b"the readings\n" * 50)

    def test_airports_and_satellite_are_not_compressed(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0), put(d, "satellite/ballymoney", 0)
            a, s = put(d, "reference/EIDW", 200), put(d, "satellite/ballymoney", 200)
            housekeep.run(d, TODAY, True)
            self.assertTrue(a.exists() and s.exists())

    def test_deleted_after_400_days_including_compressed(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0), put(d, "reference/MET-1", 0)
            keep, old = put(d, "reference/EIDW", 400), put(d, "reference/EIDW", 401)
            gz = put(d, "reference/MET-1", 401, suffix=".jsonl.gz")
            housekeep.run(d, TODAY, True)
            self.assertTrue(keep.exists())
            self.assertFalse(old.exists() or gz.exists())

    def test_a_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/MET-1", 0)
            a, b = put(d, "reference/MET-1", 20), put(d, "reference/MET-1", 500)
            got = housekeep.run(d, TODAY, False)
            self.assertEqual((got[0], got[2]), (1, 1))
            self.assertTrue(a.exists() and b.exists())
            self.assertEqual(len(list(a.parent.iterdir())), 3)

    def test_station_readings_and_other_files_are_never_touched(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/EIDW", 0)
            unit, other = put(d, "cy-0001", 900), Path(d) / "reference" / "EIDW" / "notes.jsonl"
            other.write_text("mine")
            housekeep.run(d, TODAY, True)
            self.assertTrue(unit.exists() and other.exists())

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

    def test_a_leftover_gz_that_differs_stops_that_file_only(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "reference/MET-1", 0)
            path = put(d, "reference/MET-1", 20, b"real\n")
            path.with_name(path.name + ".gz").write_bytes(gzip.compress(b"other\n"))
            problems = housekeep.run(d, TODAY, True)[4]
            self.assertEqual(len(problems), 1)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
