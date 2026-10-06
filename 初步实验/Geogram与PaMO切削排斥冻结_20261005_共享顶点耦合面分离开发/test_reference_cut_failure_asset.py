"""真实父反馈输入退化回归：不能将FP64正面积误当作GPU输入合法。"""

import json
from pathlib import Path
import unittest

import numpy as np
import trimesh

from audit_followup_candidate import sha256
from study_cut_exclusion import input_valid


class ReferenceInputTests(unittest.TestCase):
    def test_actual_third_cut_fp32_degeneracy_is_rejected(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/切削排斥父反馈退化源_v7"
        manifest = json.loads((root / "01-真实父反馈退化源冻结清单.json").read_text("utf8"))
        path = root / "clean_source.obj"
        self.assertEqual(sha256(path), manifest["files"][path.name])
        mesh = trimesh.load(path, force="mesh", process=False)
        self.assertTrue(np.all(mesh.area_faces > 0))
        self.assertTrue(mesh.is_watertight)
        triangles = mesh.vertices.astype(np.float32)[mesh.faces]
        cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        self.assertEqual(np.flatnonzero(np.all(cross == 0, axis=1)).tolist(), manifest["expected"]["fp32_zero_face_ids"])
        valid, metrics = input_valid(mesh)
        self.assertFalse(valid)
        self.assertEqual(metrics["zero_area_faces"], 0)
        self.assertEqual(metrics["fp32_zero_area_faces"], 4)


if __name__ == "__main__":
    unittest.main()
