"""检验共边同步细分的拓扑不变量和参照目标的信赖域约束。"""

import unittest
import numpy as np
import trimesh

from adaptive_cut_exclusion import refine_faces
from cut_exclusion import repair_cut_exclusion_many


class AdaptiveTests(unittest.TestCase):
    def test_adjacent_mark_patterns(self):
        mesh = trimesh.creation.icosphere(subdivisions=0)
        # 固定四个相邻面的全部标记组合，覆盖零、一、二、三个边中点模板。
        child_counts = set()
        for mask in range(16):
            marked = np.zeros(len(mesh.faces), bool)
            marked[:4] = [bool(mask & (1 << index)) for index in range(4)]
            refined, detail = refine_faces(mesh, marked)
            self.assertTrue(refined.is_watertight)
            self.assertTrue(refined.is_winding_consistent)
            self.assertEqual(refined.euler_number, mesh.euler_number)
            self.assertAlmostEqual(refined.volume, mesh.volume, places=12)
            self.assertEqual(len(detail["parent_face_ids"]), len(refined.faces))
            child_counts.update(np.bincount(detail["parent_face_ids"]).tolist())
            self.assertTrue(np.all(refined.area_faces > 0))
        self.assertEqual(child_counts, {1, 2, 3, 4})

    def test_reference_target_outside_trust_ball(self):
        mesh = trimesh.creation.box()
        mesh.apply_translation([3., 0., 0.])
        tool = trimesh.creation.box()
        target = mesh.vertices.copy() + [1., 0., 0.]
        repaired, detail = repair_cut_exclusion_many(mesh, [tool], target_vertices=target)
        self.assertTrue(detail["accepted"])
        distances = np.linalg.norm(repaired.vertices - mesh.vertices, axis=1)
        self.assertTrue(np.all(distances <= .1))
        self.assertTrue(np.all(distances > .09))


if __name__ == "__main__":
    unittest.main()
