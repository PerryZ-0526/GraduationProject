"""验证活动域边界、来源拒绝和外部绕序，防止局部维护越界。"""

import unittest
from pathlib import Path
import tempfile
import numpy as np
import trimesh
from locality_masks import external_contract, make_masks, save_obj_fp64


class LocalityTests(unittest.TestCase):
    def setUp(self):
        self.mesh = trimesh.creation.icosphere(subdivisions=2)
        self.bits = np.where(self.mesh.triangles_center[:, 2] > 0.7, 2, 1)
        self.tool = trimesh.creation.icosphere(radius=0.4)
        self.tool.apply_translation([0, 0, 1])

    def test_boundary_vertices_fixed(self):
        active, fixed = make_masks(self.mesh, self.bits, self.tool, "boolean")
        self.assertTrue(active.any() and (~active).any() and (~fixed).any())
        self.assertTrue(np.all(fixed[self.mesh.faces[~active]]))
        self.assertTrue(external_contract(self.mesh, self.mesh, np.arange(len(fixed)), active, fixed)["passed"])

    def test_missing_or_ambiguous_source_rejected(self):
        for value in (0, 3):
            bits = self.bits.copy()
            bits[0] = value
            with self.assertRaises(ValueError):
                make_masks(self.mesh, bits, self.tool, "boolean")

    def test_renumbering_and_rigid_transform(self):
        active, fixed = make_masks(self.mesh, self.bits, self.tool, "boolean")
        rng = np.random.default_rng(20261004)
        permutation = rng.permutation(len(self.mesh.vertices))
        inverse = np.argsort(permutation)
        face_order = rng.permutation(len(self.mesh.faces))
        changed = trimesh.Trimesh(self.mesh.vertices[permutation], inverse[self.mesh.faces[face_order]], process=False)
        changed.apply_transform(trimesh.transformations.rotation_matrix(0.7, [1, 2, 3]))
        changed.apply_translation([30, -12, 8])
        new_active, new_fixed = make_masks(changed, self.bits[face_order], self.tool, "boolean")
        np.testing.assert_array_equal(new_active, active[face_order])
        np.testing.assert_array_equal(new_fixed, fixed[permutation])

    def test_external_change_and_reversed_face_rejected(self):
        active, fixed = make_masks(self.mesh, self.bits, self.tool, "boolean")
        candidate = self.mesh.copy()
        candidate.vertices[np.flatnonzero(fixed)[0], 0] += 1e-6
        self.assertFalse(external_contract(self.mesh, candidate, np.arange(len(fixed)), active, fixed)["passed"])
        candidate = self.mesh.copy()
        index = np.flatnonzero(~active)[0]
        candidate.faces[index] = candidate.faces[index][::-1]
        self.assertFalse(external_contract(self.mesh, candidate, np.arange(len(fixed)), active, fixed)["passed"])

    def test_tiny_coordinates_roundtrip(self):
        # 固定小数位会将小坐标舍入；有效数字写入必须保留每个FP64值。
        mesh = self.mesh.copy()
        mesh.vertices[0, 0] = 1.842732952e-16
        mesh.vertices[1, 1] = -1.2345678901234567e-5
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tiny.obj"
            save_obj_fp64(mesh, path)
            loaded = trimesh.load(path, force="mesh", process=False)
            np.testing.assert_array_equal(mesh.vertices, loaded.vertices)
            np.testing.assert_array_equal(mesh.faces, loaded.faces)


if __name__ == "__main__":
    unittest.main()
