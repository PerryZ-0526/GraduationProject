"""真实负例证明整面排斥与完整嵌入不能代替目标覆盖检查。"""

import json
from pathlib import Path
import unittest

import trimesh

from audit_followup_candidate import sha256
from cut_exclusion import supporting_planes, certify_face_support
from exact_embedding_gate import mesh_valid_full_embedding
from run_constrained_feedback import global_geometry


class CoverageFailureTests(unittest.TestCase):
    def test_two_real_exclusion_legal_but_geometry_rejected_meshes(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/切削排斥几何覆盖负例_v12"
        data = json.loads((root / "01-排斥合法与覆盖失败真实负例清单.json").read_text("utf8"))
        for case in data["rows"]:
            with self.subTest(case=case["case"]):
                folder = root / case["case"]
                for name, digest in case["files"].items():
                    self.assertEqual(sha256(folder / name), digest)
                mesh = trimesh.load(folder / "排斥合法但几何失败候选.obj", force="mesh", process=False)
                tool = trimesh.load(folder / "首刀工具.obj", force="mesh", process=False)
                reference = trimesh.load(folder / "独立累计参照.obj", force="mesh", process=True, validate=True)
                self.assertTrue(mesh_valid_full_embedding(mesh, case["embedding_certificate"])[0])
                normals, offsets = supporting_planes(tool)
                for ids in case["frozen_face_support_ids"]:
                    self.assertTrue(certify_face_support(mesh, normals, offsets, ids)["passed"])
                # 两个独立必要条件均满足时，实际目标距离仍失败，验收不能省去该项。
                geometry = global_geometry(mesh, reference)
                self.assertGreater(geometry["probe_max_mm"], .1)
                self.assertAlmostEqual(geometry["probe_max_mm"], case["recorded_geometry"]["probe_max_mm"], places=9)


if __name__ == "__main__":
    unittest.main()
