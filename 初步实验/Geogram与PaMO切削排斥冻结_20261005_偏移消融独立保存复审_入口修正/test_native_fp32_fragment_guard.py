"""真实FP32零面积漏检与不移动顶点的同来源修复回归。"""

import json
from pathlib import Path
import unittest

import numpy as np
import trimesh

from audit_followup_candidate import sha256
from native_fp32_fragment_guard import original_invalid_faces, native_fp32_invalid_faces


class NativeFP32Tests(unittest.TestCase):
    def test_actual_zero_area_and_fixed_coordinate_repair(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/原生FP32面积修复漏检_v16"
        before = json.loads((root / "01-原生FP32面积漏检真实负例.json").read_text("utf8"))
        after = json.loads((root / "02-同源原生FP32修复证据.json").read_text("utf8"))
        for record in (before, after):
            for name, digest in record["files_sha256"].items():
                self.assertEqual(sha256(root / name), digest)
        source = trimesh.load(root / "实际第三刀源.obj", force="mesh", process=False)
        repaired = trimesh.load(root / "同源修复网格.obj", force="mesh", process=False)
        self.assertEqual(int(original_invalid_faces(source.vertices, source.faces).sum()), 0)
        self.assertEqual(np.flatnonzero(native_fp32_invalid_faces(source.vertices, source.faces)).tolist(), before["face_ids"])
        self.assertFalse(native_fp32_invalid_faces(repaired.vertices, repaired.faces).any())
        # 此例只换同来源对角线，原FP64顶点应逐点保持，而非靠坐标扰动绕过门槛。
        self.assertTrue(np.array_equal(source.vertices, repaired.vertices))
        self.assertTrue(repaired.is_watertight)
        self.assertEqual(repaired.euler_number, source.euler_number)
        self.assertTrue(after["repair_record"]["accepted"])
        self.assertLessEqual(after["repair_record"]["repair"]["geometry_probe_max_mm"], 1e-7)


if __name__ == "__main__":
    unittest.main()
