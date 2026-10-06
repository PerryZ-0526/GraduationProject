"""实际失败曲面上，法向检查前半步能保留完整投影被拒的中点。"""

import json
from pathlib import Path
import unittest

import trimesh

from audit_followup_candidate import sha256
from bidirectional_coverage_exclusion import bidirectional_midpoint_seed
from geometry_preservation_audit import MeshDistance
from audit_pamo_outputs import as_polydata


class StepBeforeOrientationTests(unittest.TestCase):
    def test_real_midpoint_is_retained_by_half_step(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/局部法向保持仍自交_v19"
        record = json.loads((root / "02-逐点回退提案诊断.json").read_text("utf8"))
        self.assertEqual(sha256(root / "独立累计参照.obj"), record["reference_sha256"])
        base = trimesh.load(root / "合法恢复基准.obj", force="mesh", process=False)
        reference = trimesh.load(root / "独立累计参照.obj", force="mesh", process=True, validate=True)
        full, full_record = bidirectional_midpoint_seed(base, reference)
        half, half_record = bidirectional_midpoint_seed(base, reference, step_fraction=.5)
        self.assertEqual(full_record["rejected_orientation_proposals"], 4)
        self.assertEqual(half_record["rejected_orientation_proposals"], 0)
        distance = MeshDistance(as_polydata(reference))
        self.assertAlmostEqual(float(distance(full.vertices).max()), record["rows"][0]["max_forward_vertex_mm"], places=9)
        self.assertAlmostEqual(float(distance(half.vertices).max()), record["rows"][1]["max_forward_vertex_mm"], places=9)
        self.assertLess(float(distance(half.vertices).max()), float(distance(full.vertices).max()))
        # 此处只检验提案，半步的完整嵌入、排斥与终态距离仍由真实批次检查。
        self.assertTrue(half.is_watertight)
        self.assertEqual(half.euler_number, base.euler_number)


if __name__ == "__main__":
    unittest.main()
