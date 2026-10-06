"""实际205报警面门控回归，完整绑定证据通过，错误摘要与非嵌入证据拒绝。"""

import json
from pathlib import Path
import unittest

import trimesh

from audit_followup_candidate import sha256
from exact_embedding_gate import mesh_valid_full_embedding


class FullEmbeddingGateTests(unittest.TestCase):
    def test_real_alarm_limit_and_certificate_binding(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/切削排斥全量嵌入门控对照_v9"
        data = json.loads((root / "01-全量嵌入门控真实对照清单.json").read_text("utf8"))
        self.assertEqual(sha256(root / data["mesh"]), data["mesh_sha256"])
        mesh = trimesh.load(root / data["mesh"], force="mesh", process=False)
        valid, metrics = mesh_valid_full_embedding(mesh, data["certificate"])
        self.assertTrue(valid)
        self.assertEqual(metrics["historical_unresolved_alarm_faces"], 205)
        for changed in ({"saved_mesh_sha256": "0" * 64}, {"embedded_closed": False}):
            self.assertFalse(mesh_valid_full_embedding(mesh, {**data["certificate"], **changed})[0])


if __name__ == "__main__":
    unittest.main()
