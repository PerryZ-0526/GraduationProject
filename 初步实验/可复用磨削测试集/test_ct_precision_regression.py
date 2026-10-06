"""冻结CT故障资产：几何通过与自由导数有限不能掩盖完整能量非有限。"""
import hashlib
import json
from pathlib import Path
import sys
import unittest
import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).parents[1] / "Geogram与PaMO组合验证"))
from locality_retriangulate import invalid_faces

ROOT = Path(__file__).parent / "CT第六事件浮点退化与能量回归_v1"


class CTPrecisionRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "01-数值退化回归资产清单.json").read_text(encoding="utf-8"))

    def test_all_frozen_bytes(self):
        self.assertEqual(len(self.manifest["files"]), 10)
        for item in self.manifest["files"]:
            with self.subTest(file=item["file"]):
                self.assertEqual(hashlib.sha256((ROOT / "inputs" / item["file"]).read_bytes()).hexdigest(), item["sha256"])

    def test_source_and_partial_still_rejected(self):
        for kind in ("original", "partial"):
            mesh = trimesh.load(ROOT / "inputs" / f"source_{kind}.obj", process=False)
            labels = json.loads((ROOT / "inputs" / f"source_{kind}_labels.json").read_text(encoding="utf-8"))["operand_bits"]
            self.assertEqual(len(labels), len(mesh.faces))
            self.assertTrue(set(labels) <= {1, 2, 3})
            self.assertTrue(mesh.is_watertight and mesh.is_winding_consistent)
            # 联合判据包含FP64与FP32，不能把原源34个总坏面误记为纯FP32计数。
            self.assertEqual(int(invalid_faces(mesh.vertices, mesh.faces).sum()), self.manifest[f"source_{kind}_invalid_faces"])
            if kind == "partial":
                self.assertTrue(np.all(mesh.area_faces > 1e-12))
                triangles = mesh.vertices.astype(np.float32).astype(float)[mesh.faces]
                zero = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0]), axis=1) == 0
                self.assertEqual(int(zero.sum()), 6)

    def test_finite_derivatives_do_not_hide_nonfinite_energy(self):
        trace = json.loads((ROOT / "inputs/gpu_expanded_diff_trace.json").read_text(encoding="utf-8"))["rows"]
        self.assertEqual(len(trace), self.manifest["gpu_trace_expected_calls"])
        self.assertEqual(sum(row["full_energy_finite"] for row in trace), 0)
        self.assertEqual(sum(not row["nonfinite_free_vertices"] for row in trace), 50)
        self.assertTrue(all(row["finite_positions"] for row in trace))
        self.assertTrue(all(row["free_vertices"] == 25 for row in trace))


if __name__ == "__main__":
    unittest.main()
