"""验证全交点计数、共享边去重、可见高度和二维多边形裁剪。"""
import unittest
import numpy as np
import trimesh
from projection import ProjectedSurface
from surface_patch import clip_polygon, polygon_area, overlay_error, verify_chart
from real_patch import BoneChart, Rejected


class ProjectionTests(unittest.TestCase):
    def test_box_shared_edge(self):
        surface = ProjectedSurface(trimesh.creation.box(extents=[2, 2, 2]))
        result = surface.query(np.array([[0., 0.], [.13, .27], [2., 0.]]))
        np.testing.assert_array_equal(result['crossings'], [2, 2, 0])
        np.testing.assert_array_equal(result['front_layers'], [1, 1, 0])
        np.testing.assert_allclose(result['z'][:2], 1.)

    def test_back_layers_not_top_fold(self):
        top = trimesh.creation.box(extents=[2, 2, 1])
        bottom = top.copy()
        bottom.apply_translation([0, 0, -3])
        result = ProjectedSurface(trimesh.util.concatenate([top, bottom])).query(np.array([[.17, .23]]))
        self.assertEqual(result['front_layers'][0], 2)
        self.assertAlmostEqual(result['z'][0], .5)

    def test_sloped_top(self):
        mesh = trimesh.creation.box(extents=[2, 2, 1])
        mesh.vertices[:, 2] += .2*mesh.vertices[:, 0]+.1*mesh.vertices[:, 1]
        xy = np.array([[.12, .25], [-.3, .1]])
        result = ProjectedSurface(mesh).query(xy)
        np.testing.assert_allclose(result['z'], .5+.2*xy[:, 0]+.1*xy[:, 1])

    def test_polygon_clipping(self):
        square = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
        triangle = np.array([[0, 0], [2, 0], [0, 2]], dtype=float)
        self.assertAlmostEqual(polygon_area(clip_polygon(triangle, square)), 1.)
        self.assertAlmostEqual(polygon_area(clip_polygon(square, square+2)), 0.)

    def test_overlay_extremum(self):
        surface = ProjectedSurface(trimesh.creation.box(extents=[2, 2, 2]))
        vertices = np.array([[-.4, -.4, 1.02], [.4, -.4, 1.02], [0, .4, 1.02]])
        error, coverage = overlay_error(surface, vertices, np.array([[0, 1, 2]]))
        np.testing.assert_allclose(error, .02, atol=1e-12)
        np.testing.assert_allclose(coverage, 0., atol=1e-12)

    def test_zero_area_height_jump_is_rejected(self):
        left = trimesh.creation.box(extents=[1, 2, 2])
        left.apply_translation([-.5, 0, 0])
        right = left.copy()
        right.apply_translation([1, 0, .3])
        surface = ProjectedSurface(trimesh.util.concatenate([left, right]))
        audit, _ = verify_chart(surface, .8)
        self.assertFalse(audit['accepted'])
        self.assertTrue(audit['interior_boundary_edges'])

    def test_chart_does_not_extrapolate(self):
        surface = ProjectedSurface(trimesh.creation.box(extents=[2, 2, 2]))
        audit, polygons = verify_chart(surface, .8)
        self.assertTrue(audit['accepted'])
        chart = BoneChart(surface, polygons)
        with self.assertRaises(Rejected):
            chart.height(np.array([[.85, 0.]]))


if __name__ == '__main__':
    unittest.main()
