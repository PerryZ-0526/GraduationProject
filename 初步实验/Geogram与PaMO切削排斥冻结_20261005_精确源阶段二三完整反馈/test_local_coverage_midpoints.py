"""局部覆盖细分提案的原顶点保持与共边连接回归。"""

import unittest
import numpy as np
import trimesh

from local_coverage_exclusion import coverage_midpoint_seed


class LocalCoverageTests(unittest.TestCase):
    def test_missing_tip_refines_without_moving_old_vertices(self):
        source = trimesh.creation.icosphere(subdivisions=0, radius=1.)
        target = source.copy()
        target.vertices[0] *= 1.5
        seed, record = coverage_midpoint_seed(source, target)
        self.assertGreater(record["marked_faces"], 0)
        self.assertGreater(len(seed.vertices), len(source.vertices))
        self.assertTrue(np.array_equal(seed.vertices[:len(source.vertices)], source.vertices))
        self.assertTrue(seed.is_watertight)
        self.assertEqual(seed.euler_number, source.euler_number)
        self.assertTrue(np.all(seed.area_faces > 0))
        self.assertTrue(all(item["new_vertex"] >= len(source.vertices) for item in record["selected"]))

    def test_already_covered_mesh_is_unchanged(self):
        source = trimesh.creation.icosphere(subdivisions=0, radius=1.)
        result, record = coverage_midpoint_seed(source, source)
        self.assertEqual(record["marked_faces"], 0)
        self.assertTrue(np.array_equal(result.vertices, source.vertices))
        self.assertTrue(np.array_equal(result.faces, source.faces))


if __name__ == "__main__":
    unittest.main()
