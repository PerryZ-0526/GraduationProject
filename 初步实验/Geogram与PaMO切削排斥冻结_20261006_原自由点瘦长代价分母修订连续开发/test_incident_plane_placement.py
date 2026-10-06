"""检查邻面约束位置的可行域、拒绝条件与原成功不变。"""
from pathlib import Path
import sys
import unittest
import numpy as np
import trimesh
from run_constrained_batch import RemoteQuality

sys.path.insert(0, str(Path(__file__).resolve().parent))
from incident_plane_collapse import balanced_parameter, incident_plane_point, collapse_degenerate


class PlacementTest(unittest.TestCase):
    def test_edge_interior_works_when_endpoints_fail(self):
        normals = np.array([[1., 0., 0.], [1., 0., 0.]])
        t = balanced_parameter(np.array([1.8e-8, 0., 0.]), normals, np.array([True, False]))
        self.assertAlmostEqual(t, .5)
        self.assertLessEqual(t * 1.8e-8, 1e-8)

    def test_off_edge_feasible_without_budget_relaxation(self):
        a, b = np.zeros(3), np.array([4e-8, 0., 0.])
        normals = np.array([[1., 1., 0.], [1., -1., 0.]]) / np.sqrt(2)
        self.assertIsNone(balanced_parameter(b - a, normals, np.array([True, False])))
        point = incident_plane_point(a, b, normals, np.array([a, b]))
        self.assertIsNotNone(point)
        self.assertGreater(abs(point[1]), 0)
        self.assertTrue((np.abs(np.sum((point - np.array([a, b])) * normals, axis=1)) <= 1e-8).all())
        self.assertLessEqual(max(np.linalg.norm(point - a), np.linalg.norm(point - b)), np.linalg.norm(b - a))

    def test_incompatible_parallel_planes_rejected(self):
        a, b = np.zeros(3), np.array([4e-8, 0., 0.])
        self.assertIsNone(incident_plane_point(a, b, np.array([[1., 0., 0.], [1., 0., 0.]]), np.array([a, b])))

    def test_zero_edge_rejected(self):
        self.assertIsNone(incident_plane_point(np.zeros(3), np.zeros(3), np.eye(3), np.zeros((3, 3))))

    def test_valid_mesh_unchanged(self):
        mesh = trimesh.creation.icosphere(subdivisions=1)
        result, labels, record = collapse_degenerate(mesh, np.ones(len(mesh.faces), dtype=int), allow_small_incident=True)
        np.testing.assert_array_equal(result.vertices, mesh.vertices)
        np.testing.assert_array_equal(result.faces, mesh.faces)
        self.assertEqual(record['remaining_invalid_faces'], 0)
        self.assertEqual(len(record['interior_collapses']), 0)


if __name__ == '__main__':
    unittest.main()
