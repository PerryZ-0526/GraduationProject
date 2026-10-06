"""检验半空间外舍入与整面排斥，避免将顶点在外误判为面在外。"""

from fractions import Fraction
import unittest

import numpy as np
import trimesh

from cut_exclusion import dot_intervals, face_separators, repair_cut_exclusion


class ExclusionTests(unittest.TestCase):
    def test_interval_contains_exact_dot(self):
        random = np.random.default_rng(20261004)
        points, normals = random.normal(size=(20, 3)), random.normal(size=(9, 3))
        lower, upper = dot_intervals(points, normals)
        for i, point in enumerate(points):
            for j, normal in enumerate(normals):
                exact = sum(Fraction(float(a)) * Fraction(float(b)) for a, b in zip(point, normal))
                self.assertLessEqual(Fraction(float(lower[i, j])), exact)
                self.assertGreaterEqual(Fraction(float(upper[i, j])), exact)

    def test_outside_vertices_do_not_certify_face(self):
        tool = trimesh.creation.box(extents=[2., 2., 2.])
        mesh = trimesh.Trimesh([[2., 0., 0.], [-2., 0., 0.], [0., 2., 0.]], [[0, 1, 2]], process=False)
        _, slack = face_separators(mesh, tool)
        self.assertLess(slack[0], 0)
        repaired, detail = repair_cut_exclusion(mesh, tool, budget_mm=.1)
        self.assertFalse(detail["accepted"])
        self.assertTrue(np.array_equal(repaired.vertices, mesh.vertices))

    def test_separated_mesh_unchanged(self):
        tool = trimesh.creation.box(extents=[1., 1., 1.])
        mesh = trimesh.creation.box(extents=[1., 1., 1.])
        mesh.apply_translation([3., 0., 0.])
        repaired, detail = repair_cut_exclusion(mesh, tool)
        self.assertTrue(detail["accepted"])
        self.assertTrue(np.array_equal(repaired.vertices, mesh.vertices))

    def test_enclosed_tool_rejected_without_anchor(self):
        tool = trimesh.creation.box(extents=[1., 1., 1.])
        mesh = trimesh.creation.box(extents=[4., 4., 4.])
        repaired, detail = repair_cut_exclusion(mesh, tool)
        self.assertFalse(detail["accepted"])
        self.assertTrue(detail["face_support_certificate"]["passed"])
        self.assertTrue(np.array_equal(repaired.vertices, mesh.vertices))
        # 该例故意把工具整个包在骨体内，说明面排斥证据不能单独推出材料不相交。
        self.assertGreater(mesh.volume, tool.volume)


if __name__ == "__main__":
    unittest.main()
