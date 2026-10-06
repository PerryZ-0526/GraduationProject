"""验证区域重建的几何、孔洞、来源边界及闭合整网格拼接。"""

import unittest
from unittest.mock import patch
import numpy as np
import trimesh
from planar_patch import rebuild_planar_regions, interior_point


class PlanarPatchTests(unittest.TestCase):
    def test_box_surface_remains_closed_and_same_shape(self):
        source = trimesh.creation.box()
        result, bits, record = rebuild_planar_regions(source, np.ones(12, int), np.ones(12, bool))
        self.assertTrue(result.is_watertight)
        self.assertTrue(result.is_winding_consistent)
        self.assertEqual(result.euler_number, source.euler_number)
        self.assertAlmostEqual(result.volume, source.volume)
        self.assertAlmostEqual(result.area, source.area)
        self.assertEqual(sum(r["accepted"] for r in record["regions"]), 6)

    def test_annulus_holes_retained(self):
        source = trimesh.creation.annulus(r_min=0.5, r_max=2, height=1, sections=24)
        result, _, record = rebuild_planar_regions(source, np.ones(len(source.faces), int), np.ones(len(source.faces), bool))
        self.assertTrue(result.is_watertight)
        self.assertEqual(result.euler_number, source.euler_number)
        self.assertAlmostEqual(result.volume, source.volume)
        self.assertGreaterEqual(sum(r.get("holes", 0) for r in record["regions"]), 2)

    def test_no_active_faces_identity(self):
        source = trimesh.creation.box()
        result, _, record = rebuild_planar_regions(source, np.ones(12, int), np.zeros(12, bool))
        np.testing.assert_array_equal(result.vertices, source.vertices)
        np.testing.assert_array_equal(result.faces, source.faces)
        self.assertEqual(record["regions"], [])

    def test_source_boundary_not_removed(self):
        source = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], [[0, 1, 2], [0, 2, 3]], process=False)
        result, labels, record = rebuild_planar_regions(source, [1, 2], [True, True])
        np.testing.assert_array_equal(source.faces, result.faces)
        np.testing.assert_array_equal(labels, [1, 2])

    def test_concave_hole_point(self):
        point = interior_point(np.array([[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3]]))
        self.assertTrue(0 < point[0] < 3 and 0 < point[1] < 3)
        self.assertFalse(point[0] > 1 and point[1] > 1)

    def test_small_generated_face_preserves_original_region(self):
        source = trimesh.Trimesh([[0,0,0],[1,0,0],[1,1,0],[0,1,0]],[[0,1,2],[0,2,3]],process=False)
        def generated(request,options):
            points=np.vstack([request["vertices"],[[.5,1e-13]]])
            return {"vertices":points,"triangles":np.array([[0,1,4],[1,2,4],[2,3,4],[3,0,4]])}
        # 新点靠近边界会生成正方向的极小面，区域必须整体拒绝并保留原网格。
        with patch("planar_patch.triangle.triangulate",side_effect=generated):
            result,_,record=rebuild_planar_regions(source,[1,1],[True,True],min_area_mm2=1e-12)
        np.testing.assert_array_equal(result.faces,source.faces)
        np.testing.assert_array_equal(result.vertices,source.vertices)
        self.assertEqual(record["regions"][0]["rejected_small_faces"],1)


if __name__ == "__main__":
    unittest.main()
