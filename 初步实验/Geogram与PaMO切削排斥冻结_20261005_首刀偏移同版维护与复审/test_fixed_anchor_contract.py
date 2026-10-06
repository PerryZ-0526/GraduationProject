"""追加固定点锚定的初态、时点、不可解除和形状约束。"""
import unittest
import numpy as np
from fixed_anchor_contract import promote_fixed_mask


class AnchorContractTests(unittest.TestCase):
    def setUp(self):
        self.initial = np.zeros((3, 3), np.float32)
        self.current = np.array([True, False, False])
        self.requested = np.array([True, True, False])

    def test_initial_exact_unchanged_new_anchor(self):
        mask, added = promote_fixed_mask(self.current, self.requested, self.initial, self.initial, 1)
        np.testing.assert_array_equal(added, [1])
        np.testing.assert_array_equal(mask, self.requested)
        np.testing.assert_array_equal(self.current, [True, False, False])

    def test_moved_or_nonfinite_new_vertex_rejected(self):
        for value in (1e-8, np.nan):
            moved = self.initial.copy()
            moved[1, 0] = value
            with self.assertRaises(ValueError):
                promote_fixed_mask(self.current, self.requested, moved, self.initial, 1)

    def test_later_new_anchor_rejected(self):
        with self.assertRaises(ValueError):
            promote_fixed_mask(self.current, self.requested, self.initial, self.initial, 2)

    def test_existing_anchor_cannot_be_removed(self):
        with self.assertRaises(ValueError):
            promote_fixed_mask(self.current, [False, True, False], self.initial, self.initial, 1)

    def test_unchanged_mask_allowed_at_later_iteration(self):
        _, added = promote_fixed_mask(self.current, self.current, self.initial, self.initial, 9)
        self.assertEqual(len(added), 0)

    def test_wrong_shapes_rejected(self):
        with self.assertRaises(ValueError):
            promote_fixed_mask(self.current, [True], self.initial, self.initial, 1)


if __name__ == "__main__":
    unittest.main()
