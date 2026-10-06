"""原始固定几何为正距离，而实际FP32编码为零距离的冻结回归。"""
import json
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "Geogram与PaMO组合验证"))
from pt_exact_reference import point_triangle_reference
from ee_exact_reference import edge_edge_reference

ROOT = Path(__file__).parent / "固定接触FP64与FP32量化对拍_v1"


class FixedContactQuantizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "01-固定接触量化对拍清单.json").read_text(encoding="utf-8"))

    def test_actual_coordinate_encoding(self):
        rows = self.manifest["rows"]
        self.assertEqual(len(rows), 20)
        self.assertEqual(sum(row["type"] == 3 for row in rows), 16)
        self.assertEqual(sum(row["type"] == 4 for row in rows), 4)
        for row in rows:
            with self.subTest(contact=row["id"]):
                self.assertTrue(all(row["fixed"]))
                actual = (np.asarray(row["points_fp64_mm"])*self.manifest["normalization_scale"]
                          + self.manifest["normalization_translation"]).astype(np.float32).astype(float)
                np.testing.assert_array_equal(actual, row["positions_fp32_normalized"])

    def test_positive_original_and_zero_encoded(self):
        for row in self.manifest["rows"]:
            with self.subTest(contact=row["id"]):
                reference = point_triangle_reference if row["type"] == 3 else edge_edge_reference
                _, physical = reference(row["points_fp64_mm"])
                _, encoded = reference(row["positions_fp32_normalized"])
                self.assertGreater(physical, 0)
                self.assertAlmostEqual(physical, row["expected_distance_fp64_mm"], delta=1e-15)
                self.assertEqual(encoded, row["expected_distance_encoded_normalized"])
                self.assertEqual(encoded, 0)


if __name__ == "__main__":
    unittest.main()
