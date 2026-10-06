"""双向覆盖提案只移动新增点与正向超差原顶点的回归。"""

import unittest
import numpy as np
import trimesh

from bidirectional_coverage_exclusion import bidirectional_midpoint_seed
from geometry_preservation_audit import MeshDistance
from audit_pamo_outputs import as_polydata


class BidirectionalCoverageTests(unittest.TestCase):
    def test_forward_protrusion_is_marked_and_other_old_vertices_fixed(self):
        target = trimesh.creation.icosphere(subdivisions=0, radius=1.)
        source = target.copy()
        source.vertices[0] *= 1.5
        before = MeshDistance(as_polydata(target))(source.vertices)
        result, record = bidirectional_midpoint_seed(source, target)
        self.assertGreater(record["forward_bad_vertices"], 0)
        fixed = before <= .1
        self.assertTrue(np.array_equal(result.vertices[:len(source.vertices)][fixed], source.vertices[fixed]))
        after = MeshDistance(as_polydata(target))(result.vertices[:len(source.vertices)])
        self.assertLess(after[0], before[0])
        self.assertTrue(result.is_watertight)
        self.assertEqual(result.euler_number, source.euler_number)
        self.assertTrue(np.all(result.area_faces > 0))

    def test_already_covered_mesh_is_unchanged(self):
        source = trimesh.creation.icosphere(subdivisions=0, radius=1.)
        result, record = bidirectional_midpoint_seed(source, source)
        self.assertEqual(record["marked_faces"], 0)
        self.assertTrue(np.array_equal(result.vertices, source.vertices))
        self.assertTrue(np.array_equal(result.faces, source.faces))


if __name__ == "__main__":
    unittest.main()
