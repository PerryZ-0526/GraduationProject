"""完整异常固定接触与GPU原几何距离查询的保存证据回归。"""
import hashlib
import json
from pathlib import Path
import sys
import unittest
import numpy as np
import trimesh
sys.path.insert(0, str(Path(__file__).parents[1] / "Geogram与PaMO组合验证"))
from pt_exact_reference import point_triangle_reference
from ee_exact_reference import edge_edge_reference

ROOT = Path(__file__).parent / "全部固定接触原几何CUDA回归_v1"


class AllFixedGeometryTests(unittest.TestCase):
    def test_frozen_bytes(self):
        manifest = json.loads((ROOT / "01-全部固定接触CUDA回归清单.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["published"])
        self.assertEqual(len(manifest["files"]), 10)
        for row in manifest["files"]:
            raw = (ROOT / row["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])
            self.assertEqual(len(raw), row["bytes"])

    def test_all_contacts_bound_to_fixed_source(self):
        record = json.loads((ROOT / "inputs/contact_audit.json").read_text(encoding="utf-8"))
        source = trimesh.load(ROOT / "inputs/source.obj", process=False)
        self.assertEqual(len(record["methods"]), 2)
        for method in record["methods"]:
            self.assertEqual(method["abnormal_contacts"], 42)
            self.assertEqual(method["quantization_cases"], 42)
            self.assertEqual(method["involving_free"], 0)
            self.assertEqual(method["diff_calls"], 50)
            self.assertEqual(method["finite_energy_calls"], 0)
            self.assertEqual(len(method["rows"]), 42)
            for row in method["rows"]:
                self.assertTrue(all(row["fixed"]))
                np.testing.assert_array_equal(source.vertices[row["original_ids"]], row["points_fp64_mm"])
                encoded = (np.asarray(row["points_fp64_mm"])*record["normalization_scale"]
                           +record["normalization_translation"]).astype(np.float32).astype(float)
                np.testing.assert_array_equal(encoded, row["positions_fp32_normalized"])
                reference = point_triangle_reference if row["type"] == 3 else edge_edge_reference
                self.assertGreater(reference(row["points_fp64_mm"])[1], 0)
                self.assertEqual(reference(encoded)[1], 0)

    def test_cuda_distance_and_true_zero_controls(self):
        data = np.load(ROOT / "inputs/queries.npz")
        gpu = json.loads((ROOT / "inputs/gpu_result.json").read_text(encoding="utf-8"))
        execution = json.loads((ROOT / "inputs/gpu_execution.json").read_text(encoding="utf-8"))
        self.assertEqual(execution["execution"]["returncode"], 0)
        self.assertEqual((gpu["queries"], gpu["passed"]), (90, 90))
        self.assertEqual(gpu["point_dtype"], "float64")
        actual = np.asarray(gpu["distances_mm"])
        references = np.array([(point_triangle_reference if kind == 3 else edge_edge_reference)(points)[1]
                               for points,kind in zip(data["points"],data["types"])])
        np.testing.assert_array_equal(data["reference"], references)
        self.assertTrue(np.all(actual[:84] > 0))
        zero = references == 0
        self.assertEqual(int(zero.sum()), 4)
        self.assertTrue(np.all(actual[zero] == 0))
        self.assertTrue(np.all(np.abs(actual-references) <= np.maximum(1e-15, references*1e-6)))


if __name__ == "__main__":
    unittest.main()
