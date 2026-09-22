"""Geogram适配器和工具离散的最小回归测试。"""
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest

import numpy as np
import trimesh


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
COMMON = HERE.parent / "共同运动记录与方法对照"
sys.path.insert(0, str(COMMON))

from geogram_baseline import (  # noqa: E402
    DEFAULT_BINARY,
    _capsule_mesh,
    _export_double_obj,
)


class GeogramAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DEFAULT_BINARY.is_file():
            raise unittest.SkipTest(f"缺少Geogram适配器: {DEFAULT_BINARY}")

    def _boolean(self, folder, operation, no_simplify=False):
        first = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
        second = first.copy()
        second.apply_translation((1.0, 0.0, 0.0))
        first_path = folder / "first.obj"
        second_path = folder / "second.obj"
        output_path = folder / f"{operation}.obj"
        _export_double_obj(first_path, first)
        _export_double_obj(second_path, second)
        command = [
            str(DEFAULT_BINARY),
            "--operation",
            operation,
        ]
        if no_simplify:
            command.append("--no-simplify")
        command.extend((str(first_path), str(second_path), str(output_path)))
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return trimesh.load(output_path, force="mesh", process=False)

    def test_adapter_supports_three_boolean_operations(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            expected_volumes = {
                "difference": 4.0,
                "intersection": 4.0,
                "union": 12.0,
            }
            for operation, expected_volume in expected_volumes.items():
                with self.subTest(operation=operation):
                    mesh = self._boolean(folder, operation)
                    self.assertTrue(mesh.is_watertight)
                    self.assertTrue(mesh.is_winding_consistent)
                    self.assertAlmostEqual(mesh.volume, expected_volume, places=10)

    def test_no_simplify_preserves_boolean_geometry(self):
        with tempfile.TemporaryDirectory() as temporary:
            mesh = self._boolean(
                Path(temporary),
                "difference",
                no_simplify=True,
            )
            self.assertTrue(mesh.is_watertight)
            self.assertTrue(mesh.is_winding_consistent)
            self.assertAlmostEqual(mesh.volume, 4.0, places=10)

    def test_tool_discretization_tightens_monotonically(self):
        primitive = {
            "start": np.array((-0.8, 0.0, 0.2)),
            "end": np.array((0.8, 0.0, 0.2)),
            "radius": 0.7,
        }
        deficits = []
        for subdivisions in (1, 2, 3, 4):
            mesh = _capsule_mesh(primitive, subdivisions=subdivisions)
            analytic_volume = (
                np.pi * primitive["radius"] ** 2 * 1.6
                + 4.0 * np.pi * primitive["radius"] ** 3 / 3.0
            )
            deficits.append(analytic_volume - mesh.volume)
            self.assertTrue(mesh.is_watertight)
            self.assertGreater(deficits[-1], 0.0)
        self.assertTrue(
            all(first > second for first, second in zip(deficits, deficits[1:]))
        )


if __name__ == "__main__":
    unittest.main()
