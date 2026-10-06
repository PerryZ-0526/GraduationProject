"""实际第三刀修复对照回归，检查合法性、拓扑、来源和几何保持。"""

import json
from pathlib import Path
import unittest

import numpy as np
import trimesh

from audit_followup_candidate import sha256
from fragment_pipeline import repair_input
from study_cut_exclusion import input_valid


class CutInputGuardTests(unittest.TestCase):
    def test_real_source_repair_preserves_contract(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/切削排斥第三刀修复对照_v8"
        manifest = json.loads((root / "01-真实修复对照冻结清单.json").read_text("utf8"))
        for name, digest in manifest["files"].items():
            self.assertEqual(sha256(root / name), digest)
        source = trimesh.load(root / "原始退化源.obj", force="mesh", process=False)
        bits = json.loads((root / "原始来源.json").read_text("utf8"))["operand_bits"]
        self.assertFalse(input_valid(source)[0])
        repaired, labels, record = repair_input(source, bits, audit=input_valid, allow_shared=True, allow_small_incident=True)
        self.assertTrue(record["accepted"])
        self.assertTrue(input_valid(repaired)[0])
        self.assertEqual(len(labels), len(repaired.faces))
        self.assertTrue(np.isin(labels, [1, 2, 3]).all())
        self.assertTrue(record["topology_preserved"])
        self.assertLessEqual(record["geometry_probe_max_mm"], 1e-7)
        self.assertEqual(input_valid(repaired)[1]["fp32_zero_area_faces"], 0)


if __name__ == "__main__":
    unittest.main()
