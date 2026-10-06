"""共同来源保留与双表面来源核对的回归检查。"""
import unittest
import numpy as np
import trimesh
from locality_cleanup import clean_provenance
from locality_masks import make_masks
from locality_diagnostic import source_region, verify_labels
from planar_patch import rebuild_planar_regions
from fragment_pipeline import repair_input
from exact_alarm_contact import mesh_valid_exact_contacts


class SharedSources(unittest.TestCase):
    def setUp(self):
        self.mesh = trimesh.creation.box()
        self.bits = np.full(len(self.mesh.faces), 3)

    def test_default_rejects_shared(self):
        with self.assertRaises(ValueError):
            clean_provenance(self.mesh, self.bits)

    def test_cleanup_preserves_shared(self):
        _, labels, _ = clean_provenance(self.mesh, self.bits, allow_shared=True)
        np.testing.assert_array_equal(labels, self.bits)

    def test_shared_faces_active(self):
        active, _ = make_masks(self.mesh, self.bits, self.mesh, "boolean", allow_shared=True)
        self.assertTrue(active.all())
        core, _, _ = source_region(self.mesh, self.bits, allow_shared=True)
        self.assertTrue(core.all())

    def test_dual_surface_validation(self):
        seam = np.empty((0,2), int)
        passed = verify_labels(self.mesh, self.bits, self.mesh, self.mesh, seam, allow_shared=True)
        self.assertTrue(passed["passed_1e_8_mm_numerical_check"])
        displaced = self.mesh.copy()
        displaced.apply_translation([0,0,2])
        failed = verify_labels(self.mesh, self.bits, self.mesh, displaced, seam, allow_shared=True)
        self.assertFalse(failed["passed_1e_8_mm_numerical_check"])

    def test_planar_regions_preserve_shared(self):
        _, labels, _ = rebuild_planar_regions(self.mesh, self.bits, np.ones(len(self.bits), bool), allow_shared=True)
        self.assertTrue(np.all(labels == 3))

    def test_unknown_bit_rejected(self):
        with self.assertRaises(ValueError):
            clean_provenance(self.mesh, np.full(len(self.bits), 4), allow_shared=True)

    def test_shared_fragment_pipeline_retains_valid_mesh(self):
        mesh, labels, details = repair_input(self.mesh, self.bits, audit=mesh_valid_exact_contacts, allow_shared=True)
        self.assertTrue(details["accepted"])
        np.testing.assert_array_equal(labels, self.bits)
        np.testing.assert_array_equal(mesh.vertices, self.mesh.vertices)


if __name__ == "__main__":
    unittest.main()
