"""Tests for the Met Éireann ceilometer reference source, on the API's real CoverageJSON shape (no network)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
import met_eireann  # noqa: E402


def coverage(times, lowest, base1, cover1):
    """A point series as Met Éireann's EDR API returns it (trimmed to the fields used)."""
    nd = lambda vals: {"type": "NdArray", "dataType": "float", "axisNames": ["t"], "shape": [len(vals)], "values": vals}
    return {"type": "Coverage", "domain": {"type": "Domain", "domainType": "PointSeries",
                                           "axes": {"x": {"values": [-7.339167]}, "y": {"values": [55.371944]}, "t": {"values": times}}},
            "ranges": {"cloud_base_height_lowest": nd(lowest), "cloud_layer_base_height_1": nd(base1),
                       "cloud_layer_cover_1": nd(cover1)},
            "custom": {"station_id": 17, "station_name": "Malin Head"}}


TIMES = ["2026-11-09T23:07:00+00:00", "2026-11-09T23:07:15+00:00", "2026-11-09T23:08:00+00:00"]


class MetEireannTest(unittest.TestCase):
    def test_decode_keeps_layers_and_drops_no_data(self):
        obs = met_eireann.decode(17, coverage(TIMES, [5700.0, -99.0, 200.0], [57.0, -99.0, 2.0], [7.0, -1.0, 9.0]))
        self.assertEqual(obs[0]["name"], "Malin Head")
        self.assertEqual(obs[0]["obs_time"], "2026-11-09T23:07:00Z")
        self.assertEqual(obs[0]["layers"], [{"base_ft": 5700.0, "oktas": 7.0, "vertical_visibility": False}], "layer heights are hundreds of feet")
        self.assertEqual(obs[1]["layers"], [], "-99 height and -1 cover are missing, not a layer")
        self.assertIsNone(obs[1]["lowest_base_ft"], "-99 means no data, never a height")
        self.assertEqual(obs[2]["layers"], [{"base_ft": 200.0, "oktas": 9.0, "vertical_visibility": True}], "9 is vertical visibility")
        self.assertIn("Met Éireann", obs[0]["attribution"])

    def test_number(self):
        for bad in (-99, -99.0, None, True, float("nan"), float("inf"), "x"):
            self.assertIsNone(met_eireann.number(bad))
        self.assertEqual(met_eireann.number(0.0), 0.0)

    def test_every_reading_kept_once(self):
        obs = met_eireann.decode(17, coverage(TIMES, [1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0]))
        thin = met_eireann.unique(obs + obs[:1])
        self.assertEqual([o["obs_time"] for o in thin], ["2026-11-09T23:07:00Z", "2026-11-09T23:07:15Z", "2026-11-09T23:08:00Z"])
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(met_eireann.store(d, thin), 3)
            self.assertEqual(met_eireann.store(d, thin), 0)
            rows = (Path(d) / "reference" / "MET-17" / "2026-11-09.jsonl").read_text().splitlines()
            self.assertEqual(json.loads(rows[0])["source"], "met-eireann-ceilometer")

    def test_empty_window(self):
        self.assertEqual(met_eireann.decode(17, coverage([], [], [], [])), [])


if __name__ == "__main__":
    unittest.main()
