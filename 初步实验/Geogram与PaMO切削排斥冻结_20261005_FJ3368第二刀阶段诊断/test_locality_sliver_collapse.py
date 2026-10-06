"""验证退化面折叠的链接条件、几何约束和面来源同步。"""

import unittest
import numpy as np
import trimesh

from locality_sliver_collapse import collapse_degenerate


def split_diagonal():
    mesh = trimesh.creation.box()
    pair = next((pair, edge) for pair, edge in zip(mesh.face_adjacency, mesh.face_adjacency_edges)
                if np.dot(mesh.face_normals[pair[0]], mesh.face_normals[pair[1]]) > 0.99)
    owners, edge = pair
    a, b = map(int, edge)
    added = len(mesh.vertices)
    vertices = np.vstack((mesh.vertices, mesh.vertices[a] + 1e-13 * (mesh.vertices[b] - mesh.vertices[a])))
    faces = [face for i, face in enumerate(mesh.faces) if i not in owners]
    for index in owners:
        face = mesh.faces[index]
        for k in range(3):
            u, v, w = map(int, (face[k], face[(k + 1) % 3], face[(k + 2) % 3]))
            if {u, v} == {a, b}:
                faces.extend(([u, added, w], [added, v, w]))
                break
    return trimesh.Trimesh(vertices, faces, process=False)


class CollapseTests(unittest.TestCase):
    def test_planar_diagonal_split_removed_and_closed_mesh_retained(self):
        original = split_diagonal()
        bits = np.ones(len(original.faces), dtype=int)
        result, labels, record = collapse_degenerate(original, bits)
        self.assertEqual(record["remaining_invalid_faces"], 0)
        self.assertEqual(len(record["collapses"]), 1)
        self.assertTrue(result.is_watertight and result.is_winding_consistent)
        self.assertEqual(result.euler_number, original.euler_number)
        self.assertEqual(len(labels), len(result.faces))
        self.assertTrue(np.all(labels == 1))
        self.assertAlmostEqual(result.volume, original.volume)

    def test_valid_mesh_unchanged(self):
        original = trimesh.creation.box()
        result, labels, record = collapse_degenerate(original, np.ones(len(original.faces)))
        np.testing.assert_array_equal(result.vertices, original.vertices)
        np.testing.assert_array_equal(result.faces, original.faces)
        self.assertEqual(record["collapses"], [])

    def test_open_boundary_edge_not_collapsed(self):
        mesh = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [0.5, 0, 0]], [[0, 1, 2]], process=False)
        result, labels, record = collapse_degenerate(mesh, [1])
        self.assertEqual(record["collapses"], [])
        self.assertEqual(record["remaining_invalid_faces"], 1)

    def test_missing_source_rejected(self):
        mesh = split_diagonal()
        with self.assertRaisesRegex(ValueError, "来源缺失"):
            collapse_degenerate(mesh, np.zeros(len(mesh.faces)))


if __name__ == "__main__":
    unittest.main()
