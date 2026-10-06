"""物理面积诊断不能混入编码退化，也不能漏掉真实物理退化。"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import numpy as np
from locality_retriangulate import invalid_faces
from run_fp64_repair_diagnostic import physical_operations


class PhysicalRepairDiagnosticTests(unittest.TestCase):
    def test_encoded_collapse_does_not_replace_physical_area(self):
        with TemporaryDirectory() as folder:
            ops = physical_operations(Path(folder))
            vertices = np.array([[100., 0, 0], [100.+1e-6, 0, 0], [100., 1, 0]])
            faces = np.array([[0, 1, 2]])
            self.assertTrue(invalid_faces(vertices, faces)[0])
            self.assertFalse(ops["invalid_faces"](vertices, faces)[0])

    def test_physical_degenerate_face_still_rejected(self):
        with TemporaryDirectory() as folder:
            ops = physical_operations(Path(folder))
            vertices = np.array([[0., 0, 0], [1e-7, 0, 0], [0., 1e-7, 0]])
            self.assertTrue(ops["invalid_faces"](vertices, np.array([[0, 1, 2]]))[0])

    def test_both_operations_use_same_private_predicate(self):
        with TemporaryDirectory() as folder:
            ops = physical_operations(Path(folder))
            for name in ("repair_degenerate", "collapse_degenerate"):
                self.assertIs(ops[name].__globals__["invalid_faces"], ops["invalid_faces"])
            self.assertIsNot(ops["invalid_faces"], invalid_faces)


if __name__ == "__main__":
    unittest.main()
