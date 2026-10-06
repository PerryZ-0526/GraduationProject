"""严格无变化识别不得由近似距离、反向面或工具来源冒充。"""

import unittest
import numpy as np
import trimesh
from exact_oriented_surface_identity import exact_oriented_surface_identity


class IdentityTest(unittest.TestCase):
    def setUp(self):
        self.parent = trimesh.creation.box()

    def test_reindexed_and_cyclic_faces_match(self):
        faces = np.roll(self.parent.faces[::-1], 1, axis=1)
        source = trimesh.Trimesh(self.parent.vertices[::-1], len(self.parent.vertices) - 1 - faces, process=False)
        self.assertTrue(exact_oriented_surface_identity(self.parent, source, np.ones(len(faces)))["same"])

    def test_reversed_face_and_duplicate_do_not_match(self):
        source = self.parent.copy()
        source.faces[0] = source.faces[0][::-1]
        self.assertFalse(exact_oriented_surface_identity(self.parent, source, np.ones(len(source.faces)))["same"])
        source = trimesh.Trimesh(self.parent.vertices, np.vstack([self.parent.faces, self.parent.faces[0]]), process=False)
        self.assertFalse(exact_oriented_surface_identity(self.parent, source, np.ones(len(source.faces)))["same"])

    def test_one_ulp_and_tool_origin_do_not_match(self):
        source = self.parent.copy()
        source.vertices[0, 0] = np.nextafter(source.vertices[0, 0], np.inf)
        self.assertFalse(exact_oriented_surface_identity(self.parent, source, np.ones(len(source.faces)))["same"])
        bits = np.ones(len(self.parent.faces))
        bits[0] = 3
        self.assertFalse(exact_oriented_surface_identity(self.parent, self.parent, bits)["same"])


if __name__ == "__main__":
    unittest.main()
