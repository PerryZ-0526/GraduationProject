"""相同碎片修复候选的旧回滚与完整嵌入门控接受回归。"""

import json
from pathlib import Path
import unittest

import numpy as np
import trimesh

from audit_followup_candidate import sha256
from fragment_pipeline import repair_input
from study_cut_exclusion import input_valid
from exact_embedding_gate import mesh_input_valid_full_embedding, stored_mesh_sha256


class RepairedInputGateTests(unittest.TestCase):
    def test_same_repair_preserves_true_zero_topology_and_geometry_guards(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/切削排斥退化修复后门控对照_v11"
        data = json.loads((root / "01-修复后报警门控同源对照清单.json").read_text("utf8"))
        for name, digest in data["files"].items():
            self.assertEqual(sha256(root / name), digest)
        mesh = trimesh.load(root / "原始四退化面源.obj", force="mesh", process=False)
        bits = json.loads((root / "原始来源标签.json").read_text("utf8"))["operand_bits"]
        old, _, failure = repair_input(mesh, bits, audit=input_valid, allow_shared=True, allow_small_incident=True)
        self.assertFalse(failure["accepted"])
        self.assertEqual(failure["remaining_invalid_faces"], 0)
        self.assertTrue(np.array_equal(old.faces, mesh.faces))
        # 唯一变化是对同一修复候选使用其已保存完整证明；原真退化输入仍不能被此证明接受。
        audit = lambda candidate: mesh_input_valid_full_embedding(candidate, data["certificate"])
        self.assertFalse(audit(mesh)[0])
        repaired, labels, record = repair_input(mesh, bits, audit=audit, allow_shared=True, allow_small_incident=True)
        self.assertTrue(record["accepted"])
        self.assertTrue(record["topology_preserved"])
        self.assertEqual(record["remaining_invalid_faces"], 0)
        self.assertLessEqual(record["geometry_probe_max_mm"], 1e-7)
        self.assertEqual(stored_mesh_sha256(repaired), data["files"]["修复后合法源.obj"])
        self.assertEqual(labels.tolist(), json.loads((root / "修复后来源标签.json").read_text("utf8"))["operand_bits"])


if __name__ == "__main__":
    unittest.main()
