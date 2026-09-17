import json
import unittest

import numpy as np

from real_ct_state import (
    JOINT,
    SCENARIOS,
    SEQUENCE,
    evaluate_sequence,
    load_plan_module,
    nominal_state,
    plan_samples,
    uncertain_state,
)


class RealCtStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(SCENARIOS.read_text(encoding="utf-8"))
        cls.plan = load_plan_module()

    def test_piecewise_polar_quadrature_has_exact_disk_area(self):
        xy, weights, bands = plan_samples(
            self.config["quadrature"]["radial_intervals_mm"],
            32,
            64,
        )
        radius = self.config["analysis_region"]["radius_mm"]
        self.assertAlmostEqual(float(weights.sum()), np.pi * radius**2, places=11)
        self.assertEqual(len(xy), len(weights))
        self.assertEqual(set(np.unique(bands)), {0, 1, 2})

    def test_nominal_volume_identities(self):
        initial = np.array([2.0, 1.0, 1.0])
        current = np.array([1.0, -1.0, 0.5])
        target = np.array([0.0, 0.0, 0.75])
        weights = np.ones(3)
        state = nominal_state(initial, current, target, weights)
        self.assertAlmostEqual(
            state["planned_removal_volume_mm3"],
            state["achieved_within_plan_volume_mm3"]
            + state["remaining_within_plan_volume_mm3"],
        )
        self.assertAlmostEqual(
            state["actual_removed_volume_mm3"],
            state["achieved_within_plan_volume_mm3"]
            + state["overcut_within_plan_volume_mm3"],
        )
        self.assertGreater(state["overcut_within_plan_volume_mm3"], 0.0)

    def test_uncertainty_interval_contains_nominal_and_expands(self):
        xy = np.array([[0.0, 0.0], [1.0, 0.0]])
        weights = np.ones(2)
        initial = np.array([2.0, 2.0])
        current = np.array([1.0, 0.5])
        target = np.array([0.0, 0.0])
        nominal = nominal_state(initial, current, target, weights)
        intervals = [
            uncertain_state(
                initial,
                current,
                target,
                xy,
                weights,
                scenario,
                0.1,
            )
            for scenario in self.config["scenarios"]
        ]
        for interval in intervals:
            lower, upper = interval[
                "actual_removed_volume_interval_mm3"
            ]
            self.assertLessEqual(lower, nominal["actual_removed_volume_mm3"])
            self.assertGreaterEqual(upper, nominal["actual_removed_volume_mm3"])
        narrow = intervals[1]["remaining_within_plan_volume_interval_mm3"]
        wide = intervals[2]["remaining_within_plan_volume_interval_mm3"]
        self.assertGreaterEqual(wide[1] - wide[0], narrow[1] - narrow[0])

    def test_real_ct_sequence_maps_to_monotone_local_state(self):
        sequence = np.load(SEQUENCE)
        joint = np.load(JOINT)
        np.testing.assert_array_equal(sequence["snapshots"][0], joint["vertices"])
        rows, _ = evaluate_sequence(
            sequence,
            self.plan,
            self.config,
            32,
            64,
        )
        actual = np.array(
            [row["actual_removed_volume_mm3"] for row in rows]
        )
        remaining = np.array(
            [row["remaining_within_plan_volume_mm3"] for row in rows]
        )
        self.assertTrue(np.all(np.diff(actual) >= -1e-10))
        self.assertTrue(np.all(np.diff(remaining) <= 1e-10))
        self.assertEqual(rows[0]["completion_fraction"], 0.0)
        self.assertGreater(rows[-1]["completion_fraction"], 0.04)
        self.assertLess(rows[-1]["completion_fraction"], 0.06)
        self.assertEqual(rows[-1]["overcut_within_plan_volume_mm3"], 0.0)


if __name__ == "__main__":
    unittest.main()
