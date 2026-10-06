"""模拟GPU接口核对锚点更新后完整能量重算顺序，不冒充CUDA验证。"""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np


class ArrayView:
    def __init__(self, values):
        self.values = values
    def __getitem__(self, item):
        return ArrayView(self.values[item])
    def detach(self):
        return self
    def cpu(self):
        return self
    def numpy(self):
        return self.values


class BaseSystem:
    def set_fixed(self, fixed):
        self.base_fixed = np.asarray(fixed).copy()


class AnchorEnergyRefreshTests(unittest.TestCase):
    def setUp(self):
        warp = SimpleNamespace(to_torch=ArrayView,
            array=lambda values, **kwargs: np.asarray(values).copy())
        base = SimpleNamespace(CollisionProtectedSystem=BaseSystem)
        path = Path(__file__).with_name("anchored_geometry_system.py")
        spec = importlib.util.spec_from_file_location("isolated_anchor_energy_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"warp": warp, "preserved_geometry_system": base}):
            spec.loader.exec_module(module)
        self.system = module.CollisionProtectedSystem()
        self.system.q = np.zeros((3, 3), np.float32)
        self.system.original_fixed_encoded = ArrayView(self.system.q.copy())
        self.system.original_fixed_host = np.array([True, False, False])
        self.system.original_fixed_mask = self.system.original_fixed_host.astype(np.int32)
        self.system.n_particles = 3
        self.system.device = "mock"
        self.system.diff_calls = 1
        self.system.anchor_updates = []
        self.system.write_anchor_record = lambda: None
        self.system.energy = ArrayView(np.array([np.inf], np.float32))
        self.calls = 0

    def install_energy(self, value):
        def recompute():
            # 完整能量重算发生在两个固定掩码都已更新之后。
            np.testing.assert_array_equal(self.system.base_fixed, [True, True, False])
            np.testing.assert_array_equal(self.system.original_fixed_mask, [1, 1, 0])
            self.calls += 1
            self.system.energy.values[0] = value
        self.system._compute_energy = recompute

    def test_promoted_mask_recomputes_complete_energy_after_fixed_update(self):
        self.install_energy(4.25)
        self.system.set_fixed([True, True, False])
        self.assertEqual(self.calls, 1)
        self.assertEqual(float(self.system.energy.values[0]), 4.25)
        update = self.system.anchor_updates[0]
        self.assertTrue(update["full_energy_recomputed"])
        self.assertTrue(update["recomputed_energy_finite"])
        self.assertEqual(update["added_vertices"], [1])

    def test_nonfinite_recomputed_energy_is_recorded_as_failure(self):
        self.install_energy(np.inf)
        self.system.set_fixed([True, True, False])
        self.assertEqual(self.calls, 1)
        self.assertFalse(self.system.anchor_updates[0]["recomputed_energy_finite"])
        self.assertIsNone(self.system.anchor_updates[0]["recomputed_energy"])
        self.assertTrue(np.isinf(self.system.energy.values[0]))

    def test_unchanged_mask_does_not_reset_energy(self):
        self.install_energy(4.25)
        self.system.set_fixed([True, False, False])
        self.assertEqual(self.calls, 0)
        self.assertEqual(self.system.anchor_updates, [])
        self.assertTrue(np.isinf(self.system.energy.values[0]))


if __name__ == "__main__":
    unittest.main()
