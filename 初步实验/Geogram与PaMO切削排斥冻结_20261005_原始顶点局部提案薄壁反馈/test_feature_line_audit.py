"""固定扫描线能检测厚度、间隙及填孔，边界歧义不能计作通过。"""
import unittest
import trimesh
from feature_line_audit import material_intervals, compare_intervals


class FeatureLineTests(unittest.TestCase):
    def test_box_thickness(self):
        mesh = trimesh.creation.box(extents=[4, 4, .03])
        intervals = material_intervals(mesh, 2, [.173, .281, 0])
        self.assertAlmostEqual(intervals[0][1]-intervals[0][0], .03)

    def test_narrow_gap(self):
        pieces = []
        for sign in (-1, 1):
            mesh = trimesh.creation.box(extents=[2, 4, 4])
            mesh.apply_translation([sign*1.015, 0, 0])
            pieces.append(mesh)
        mesh = trimesh.util.concatenate(pieces)
        reference = material_intervals(mesh, 0, [0, .173, .281])
        result = compare_intervals(reference, reference)
        self.assertAlmostEqual(result["reference_central_void_width_mm"], .03)

    def test_filled_gap_detected(self):
        result = compare_intervals([[-2, -.015], [.015, 2]], [[-2, 2]])
        self.assertFalse(result["interval_count_matches"])
        self.assertFalse(result["central_void_presence_matches"])

    def test_polygonal_hole(self):
        mesh = trimesh.creation.annulus(r_min=.3, r_max=2, height=2, sections=64)
        intervals = material_intervals(mesh, 0, [0, .037, .173])
        self.assertEqual(len(intervals), 2)
        result = compare_intervals(intervals, intervals)
        self.assertGreater(result["reference_central_void_width_mm"], .5)
        self.assertEqual(result["central_void_width_difference_mm"], 0)

    def test_width_change_detected(self):
        result = compare_intervals([[-.015, .015]], [[-.01, .01]])
        self.assertAlmostEqual(result["maximum_material_width_difference_mm"], .01)

    def test_coplanar_rejected(self):
        with self.assertRaises(ValueError):
            material_intervals(trimesh.creation.box(extents=[2, 2, 2]), 0, [0, 1, .173])

    def test_reversed_surface_rejected(self):
        mesh = trimesh.creation.box(extents=[2, 2, 2])
        mesh.invert()
        with self.assertRaises(ValueError):
            material_intervals(mesh, 0, [0, .173, .281])


if __name__ == "__main__":
    unittest.main()
