"""Tests for turning the Nano's USB lines into readings (no Nano or pyserial needed)."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import serial_station  # noqa: E402

WHEN = datetime(2026, 11, 20, 23, 14, tzinfo=timezone.utc)

try:
    from jsonschema import Draft202012Validator
    SCHEMA = Draft202012Validator(json.loads((Path(__file__).parent.parent / "schemas" / "reading.schema.json").read_text()))
except ImportError:
    SCHEMA = None


class SerialStationTest(unittest.TestCase):
    def check(self, r):
        if SCHEMA:
            errors = [e.message for e in SCHEMA.iter_errors(r)]
            self.assertEqual(errors, [], r)

    def test_full_line(self):
        v = serial_station.parse("CY v=1 sky=-18.41 amb=5.20 air=6.10 hum=81.0 pres=1012.3 chip=60")
        r = serial_station.reading(v, "cy-0001", 1, 1, WHEN)
        self.assertEqual(r["readings"], {"sky_c": -18.41, "air_c": 6.1, "humidity": 81.0, "pressure_hpa": 1012.3, "sensor_c": 5.2})
        self.assertEqual(r["flags"], [])
        self.assertEqual(r["hw"], "nano-usb")
        self.check(r)

    def test_bmp280_has_no_humidity(self):
        v = serial_station.parse("CY v=1 sky=-20.00 amb=4.00 air=5.00 pres=1010.0 chip=58")
        r = serial_station.reading(v, "cy-0001", 1, 2, WHEN)
        self.assertNotIn("humidity", r["capabilities"])
        self.assertIn("bmp280", r["flags"])
        self.check(r)

    def test_missing_sensor_is_flagged_not_invented(self):
        v = serial_station.parse("CY v=1 air=6.10 hum=81.0 pres=1012.3 chip=60 err=mlx")
        r = serial_station.reading(v, "cy-0001", 1, 3, WHEN)
        self.assertNotIn("sky_c", r["readings"])
        self.assertIn("sensor_read_failed", r["flags"])

    def test_other_lines_and_junk_are_ignored(self):
        self.assertIsNone(serial_station.parse("CY hello v=1 nano-usb"))
        self.assertIsNone(serial_station.parse("garbage"))
        v = serial_station.parse("CY v=1 sky=nan air=oops chip=60")
        self.assertNotIn("sky_c", v)
        self.assertNotIn("air_c", v)

    def test_boot_counts_up_and_local_write(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(serial_station.next_boot(d, "cy-0001"), 1)
            self.assertEqual(serial_station.next_boot(d, "cy-0001"), 2)
            v = serial_station.parse("CY v=1 sky=-18.41 amb=5.20 air=6.10 hum=81.0 pres=1012.3 chip=60")
            serial_station.write_local(d, serial_station.reading(v, "cy-0001", 2, 1, WHEN))
            rows = (Path(d) / "cy-0001" / "2026-11-20.jsonl").read_text().splitlines()
            self.assertEqual(json.loads(rows[0])["seq"], 1)


if __name__ == "__main__":
    unittest.main()
