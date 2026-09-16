"""共边拓扑、原外部保持和多环拒绝的最小回归测试。"""
import unittest
import numpy as np
import trimesh
from stitch import boundary_of, stitch_candidate, topology, Rejected, audit_candidate, ProjectedSurface


class FlatChart:
    def height(self, xy):
        return np.ones(len(xy))


class StitchTests(unittest.TestCase):
    def test_box_shared_indices(self):
        source = trimesh.creation.box(extents=[4, 4, 2])
        removed = np.flatnonzero(source.face_normals[:, 2] > .9)
        original_vertices, original_faces = source.vertices.copy(), source.faces.copy()
        candidate = stitch_candidate(source, removed, FlatChart(), .08)
        self.assertTrue(topology(candidate['whole'])['watertight'])
        self.assertTrue(topology(candidate['whole'])['winding'])
        self.assertEqual(topology(candidate['whole'])['euler'], 2)
        np.testing.assert_array_equal(candidate['whole'].faces[:candidate['keep'].sum()], source.faces[candidate['keep']])
        np.testing.assert_array_equal(candidate['whole'].vertices[:len(source.vertices)], source.vertices)
        np.testing.assert_array_equal(source.vertices, original_vertices)
        np.testing.assert_array_equal(source.faces, original_faces)
        audit, _, _ = audit_candidate(ProjectedSurface(source), candidate)
        self.assertTrue(audit['accepted'])

    def test_skinny_watertight_candidate_rejected(self):
        # 用窄长顶面显式构造差面，水密不能替代逐面质量验收。
        source = trimesh.creation.box(extents=[4, .1, 2])
        removed = np.flatnonzero(source.face_normals[:, 2] > .9)
        candidate = stitch_candidate(source, removed, FlatChart(), .08)
        audit, _, _ = audit_candidate(ProjectedSurface(source), candidate)
        self.assertTrue(audit['watertight'])
        self.assertGreater(audit['bad_faces'], 0)
        self.assertFalse(audit['accepted'])

    def test_disconnected_boundary_rejected(self):
        with self.assertRaises(Rejected):
            boundary_of(np.array([[0, 1, 2], [3, 4, 5]]))

    def test_nonmanifold_rejected(self):
        with self.assertRaises(Rejected):
            boundary_of(np.array([[0, 1, 2], [1, 0, 3], [0, 1, 4]]))


if __name__ == '__main__':
    unittest.main()
