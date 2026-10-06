"""真实输入报警截断、证据绑定及输入输出面积协议的回归。"""

import json
from pathlib import Path
import unittest

import trimesh

from audit_followup_candidate import sha256
from exact_embedding_gate import mesh_input_valid_full_embedding, mesh_valid_full_embedding, stored_mesh_sha256


class InputFullEmbeddingTests(unittest.TestCase):
    def test_real_257_alarm_input_and_binding(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/切削排斥输入全量门控对照_v10"
        data = json.loads((root / "01-输入完整嵌入门控对照清单.json").read_text("utf8"))
        for name, digest in data["files"].items():
            self.assertEqual(sha256(root / name), digest)
        mesh = trimesh.load(root / data["mesh"], force="mesh", process=False)
        valid, metrics = mesh_input_valid_full_embedding(mesh, data["certificate"])
        self.assertTrue(valid)
        self.assertEqual(metrics["historical_unresolved_alarm_faces"], 257)
        for change in ({"saved_sha256": "0" * 64}, {"embedded_closed": False}):
            self.assertFalse(mesh_input_valid_full_embedding(mesh, {**data["certificate"], **change})[0])

    def test_input_true_zero_and_output_threshold_remain_distinct(self):
        mesh = trimesh.creation.box(extents=[1e-7, 1e-7, 1e-7])
        # 解析立方体用于门控逻辑控制，输入极小正面积仍允许，输出原面积门槛仍拒绝。
        certificate = {"embedded_closed": True, "saved_sha256": stored_mesh_sha256(mesh)}
        self.assertTrue(mesh_input_valid_full_embedding(mesh, certificate)[0])
        self.assertFalse(mesh_valid_full_embedding(mesh, certificate)[0])
        assets = Path(__file__).parents[1] / "可复用磨削测试集/切削排斥父反馈退化源_v7"
        # 即使提供绑定的嵌入标志，真实FP32零面积仍必须拒绝，不靠自交证据绕过面积检查。
        source = trimesh.load(assets / "clean_source.obj", force="mesh", process=False)
        certificate = {"embedded_closed": True, "saved_sha256": stored_mesh_sha256(source)}
        self.assertFalse(mesh_input_valid_full_embedding(source, certificate)[0])


if __name__ == "__main__":
    unittest.main()
