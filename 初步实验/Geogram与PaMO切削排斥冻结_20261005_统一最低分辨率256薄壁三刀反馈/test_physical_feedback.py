"""物理面积反馈保留原版分支、参照独立性及原输入保护。"""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import trimesh
import physical_feedback_gate as gate
from physical_input_repair import SOURCE, repair_physical_input
from run_physical_geometry_feedback import build_entry


class PhysicalFeedbackTests(unittest.TestCase):
    def test_original_branch_keeps_original_cleanup(self):
        with patch.object(gate, "original_clean_for_backend", return_value="original") as original, \
             patch.object(gate, "repair_physical_input") as physical:
            self.assertEqual(gate.clean_for_backend("mesh", "bits", "full"), "original")
            original.assert_called_once_with("mesh", "bits", "full")
            physical.assert_not_called()

    def test_valid_input_has_no_unnecessary_operations(self):
        mesh = trimesh.creation.box()
        repaired, labels, record = repair_physical_input(mesh, np.ones(len(mesh.faces), int))
        self.assertTrue(record["accepted_for_fixed_geometry_backend"])
        self.assertEqual(record["steps"], [])
        np.testing.assert_array_equal(repaired.vertices, mesh.vertices)
        np.testing.assert_array_equal(repaired.faces, mesh.faces)
        self.assertEqual(len(labels), len(mesh.faces))

    def test_entry_preserves_reference_and_original_gates(self):
        root = Path(__file__).resolve().parent
        entry = build_entry((root/"run_preserved_geometry_feedback.py").read_text(encoding="utf-8"),
            (root/"guarded_reference_recovery.py").read_text(encoding="utf-8"))
        ast.parse(entry)
        self.assertIn("controller.clean_for_backend = physical_clean_for_backend", entry)
        self.assertIn("from physical_input_repair import repair_physical_input as repair_preserved_input", entry)
        self.assertIn("check_preserved_mesh", entry)
        self.assertIn("require_fixed_degenerate_faces", entry)
        for condition in ("fp64_bad == 0", "distance <= 1e-7", "topology", "repair_degenerate,collapse_degenerate,repair_degenerate"):
            self.assertIn(condition, SOURCE)


if __name__ == "__main__":
    unittest.main()
