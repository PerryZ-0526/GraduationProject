"""验证数值碎片清理的来源映射和拒绝边界。"""

import unittest
import numpy as np
import trimesh

from locality_cleanup import clean_provenance


class CleanupTests(unittest.TestCase):
    def test_collapsed_face_removed_and_labels_follow_original_faces(self):
        vertices = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0], [1 + 1e-12, 0, 0]])
        mesh = trimesh.Trimesh(vertices, [[0, 1, 3], [0, 1, 2]], process=False)
        clean, bits, record = clean_provenance(mesh, [2, 1])
        np.testing.assert_array_equal(bits, [1])
        self.assertEqual(record["surviving_original_face_ids"], [1])
        self.assertEqual(record["removed_collapsed_faces"], 1)
        self.assertLess(record["max_raw_vertex_to_clean_vertex_mm"], 1e-7)

    def test_thin_unique_triangle_is_not_silently_deleted(self):
        mesh = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [0.5, 1e-10, 0]], [[0, 1, 2]], process=False)
        clean, bits, record = clean_provenance(mesh, [2])
        self.assertEqual(len(clean.faces), 1)
        self.assertEqual(record["removed_collapsed_faces"], 0)

    def test_source_conflict_after_welding_rejected(self):
        mesh = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1 + 1e-12, 0, 0]],
                              [[0, 1, 2], [0, 3, 2]], process=False)
        with self.assertRaisesRegex(ValueError, "重复面"):
            clean_provenance(mesh, [1, 2])

    def test_missing_source_rejected(self):
        mesh = trimesh.creation.icosphere(subdivisions=0)
        with self.assertRaisesRegex(ValueError, "来源缺失"):
            clean_provenance(mesh, np.zeros(len(mesh.faces)))

    def test_empty_after_collapse_rejected(self):
        mesh = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [1 + 1e-12, 0, 0]], [[0, 1, 2]], process=False)
        with self.assertRaisesRegex(ValueError, "无三角面"):
            clean_provenance(mesh, [1])


if __name__ == "__main__":
    unittest.main()
