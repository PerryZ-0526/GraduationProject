"""真实合法超差对象可进入分布观察，非法提案不能因面积比例好而通过。"""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import run_reference_cut_feedback
import trimesh
from distribution_ranked_exclusion import distribution_ranked_exclusion


class ActualRankedTest(unittest.TestCase):
    def test_known_legal_candidate_not_rejected_by_maximum(self):
        root = Path(r"D:\GraduationProject_切削排斥证据\可复用磨削测试集\规范排序合法嵌入仍超差_v25")
        proof = json.loads((root / "同源及候选证据.json").read_text("utf8"))
        attempt = proof["best"]["attempt"]
        candidate = trimesh.load(root / "最小超差合法候选.obj", force="mesh", process=False)
        source = trimesh.load(root / "维护源.obj", force="mesh", process=False)
        reference = trimesh.load(root / "累计参照.obj", force="mesh", process=True)
        bits = json.loads((root / "维护源标签.json").read_text("utf8"))["operand_bits"]
        anchors = attempt["exclusion"]["outside_anchor_certificate"]
        anchor = anchors if isinstance(anchors, dict) else anchors[0]

        def replay(raw, tools, target, remember):
            # 只复用已冻结的真实合法提案，测试新排序与停止语义，不伪称重做精确求解。
            remember(candidate, None, None, None)
            return candidate, {"accepted": False, "attempts": [attempt]}

        with patch("distribution_ranked_exclusion.stepwise_coverage_exclusion", replay):
            selected, record = distribution_ranked_exclusion(candidate, [], reference, source, bits, lambda *args: anchor)
        self.assertTrue(record["accepted"])
        self.assertIsNone(record["fixed_geometry_acceptance_threshold"])
        self.assertGreater(record["geometry"]["worst_probe_max_mm"], .1)
        self.assertEqual(record["acceptance_scope"], "legality_for_geometry_observation_only")
        np.testing.assert_array_equal(selected.vertices, candidate.vertices)

        invalid = dict(attempt, mesh_valid=False)
        with patch("distribution_ranked_exclusion.stepwise_coverage_exclusion", return_value=(candidate, {"accepted": False, "attempts": [invalid]})):
            _, rejected = distribution_ranked_exclusion(candidate, [], reference, source, bits, lambda *args: anchor)
        self.assertFalse(rejected["accepted"])


if __name__ == "__main__":
    unittest.main()
