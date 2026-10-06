"""真实局部步长回归：距离改善仍保留完整自交负例。"""

import hashlib
import json
from pathlib import Path
import unittest

import numpy as np
import trimesh
import run_reference_cut_feedback
from bidirectional_coverage_exclusion import bidirectional_midpoint_seed
from exact_embedding_gate import stored_mesh_sha256


class ActualOrientationLimitTest(unittest.TestCase):
    def test_actual_seed_default_unchanged_and_limited_still_not_certified(self):
        root = Path(__file__).resolve().parents[1] / "可复用磨削测试集/线性法向步长局部恢复_v21"
        record = json.loads((root / "01-线性法向限步同源提案冻结.json").read_text("utf8"))
        for name, expected in record["files"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected)
        base = trimesh.load(root / "合法恢复基准.obj", force="mesh", process=False)
        reference = trimesh.load(root / "独立累计参照.obj", force="mesh", process=True, validate=True)
        old, old_details = bidirectional_midpoint_seed(base, reference)
        limited, details = bidirectional_midpoint_seed(base, reference, orientation_limited=True)
        self.assertEqual(stored_mesh_sha256(old), record["files"]["原完整投影提案.obj"])
        self.assertEqual(stored_mesh_sha256(limited), record["files"]["线性法向限步提案.obj"])
        self.assertEqual(old_details["rejected_orientation_proposals"], 4)
        self.assertEqual(details["rejected_orientation_proposals"], 0)
        self.assertTrue(np.isfinite(limited.vertices).all())
        self.assertTrue(limited.is_watertight)
        self.assertLess(record["new"]["geometry"]["probe_max_mm"], record["old"]["geometry"]["probe_max_mm"])
        self.assertGreater(record["new"]["geometry"]["probe_max_mm"], .1)
        proof = json.loads((root / "02-同源提案完整嵌入负例.json").read_text("utf8"))
        # 此处核对已实际执行的全量检查与同一输出绑定，不将单元测试称为重新运行CGAL。
        for row in proof["rows"]:
            self.assertEqual(row["saved_sha256"], record["files"][row["file"]])
            self.assertEqual(row["checks"]["self_intersection_pairs"], 3)
            self.assertFalse(row["checks"]["embedded_closed"])


if __name__ == "__main__":
    unittest.main()
