"""实际超差候选的面积分布回归，避免最大顶点误差代替表面比例。"""

import hashlib
import json
from pathlib import Path
import unittest

import run_reference_cut_feedback
import trimesh
from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution


class ActualDistributionTest(unittest.TestCase):
    def test_legal_candidate_maximum_and_area_are_different_evidence(self):
        root = Path(r"D:\GraduationProject_切削排斥证据\可复用磨削测试集\规范排序合法嵌入仍超差_v25")
        manifest = json.loads((root / "01-规范排序合法超差冻结清单.json").read_text("utf8"))
        for item in manifest["files"]:
            self.assertEqual(hashlib.sha256((root / item["file"]).read_bytes()).hexdigest(), item["sha256"])
        candidate = trimesh.load(root / "最小超差合法候选.obj", force="mesh", process=False)
        source = trimesh.load(root / "维护源.obj", force="mesh", process=False)
        reference = trimesh.load(root / "累计参照.obj", force="mesh", process=True)
        geometry = geometry_error_distribution(candidate, reference)
        maximum = max(geometry["vertices_forward"]["max_mm"], geometry["vertices_reverse"]["max_mm"])
        self.assertGreater(maximum, .1)
        self.assertEqual(geometry["minimum_bidirectional_area_fraction_within_0_1_mm"], 1.)
        bits = json.loads((root / "维护源标签.json").read_text("utf8"))["operand_bits"]
        local = cutting_surface_distribution(candidate, source, bits)
        # 小切削区必须单独足量采样，不能把全骨中它占约千分之一当作局部准确性。
        self.assertEqual(local["source_faces"], 289)
        self.assertEqual(local["distribution"]["count"], 8192)
        self.assertEqual(local["distribution"]["within_distance_fraction"]["0.1"], 1.)
        self.assertAlmostEqual(local["distribution"]["quantiles_mm"]["0.95"], .036359086174623856, places=8)


if __name__ == "__main__":
    unittest.main()
