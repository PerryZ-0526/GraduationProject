from copy import deepcopy
from pathlib import Path
import sys
import unittest

import numpy as np

from motion_record import (
    RecordError,
    actual_material_field,
    capsule_field,
    classify_points,
    load_document,
    planned_material_field,
    replay_case,
    sample_box,
    validate_document,
)


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "计划裁剪特征重建"))
from clipped_patch import audit_candidate, generate

from surface_methods import (
    capsule_vertical_interval,
    height_surface,
    mesh_quality,
    mesh_topology,
    source_constrained_height_surface,
    source_fitted_height_surface,
    top_connected_height,
)
from state_metrics import planned_state_metrics
from geogram_baseline import effective_primitives


class MotionRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = load_document()
        cls.policy = cls.document["replay_policy"]
        cls.cases = {case["id"]: case for case in cls.document["cases"]}

    def test_all_six_cases_match_fixed_answers(self):
        self.assertEqual(len(self.cases), 6)
        for case in self.cases.values():
            with self.subTest(case=case["id"]):
                replay = replay_case(case, self.policy)
                expected = case["expected"]
                self.assertEqual(replay["accepted_event_ids"], expected["accepted_event_ids"])
                self.assertEqual(replay["late_event_ids"], expected["late_event_ids"])
                self.assertEqual(len(replay["primitives"]), expected["primitive_count"])
                self.assertEqual(
                    replay["connected_segment_count"],
                    expected["connected_segment_count"],
                )
                probes = [item["point_mm"] for item in expected["point_states"]]
                states = classify_points(probes, case, replay).tolist()
                self.assertEqual(states, [item["state"] for item in expected["point_states"]])

    def test_repeated_path_does_not_change_material(self):
        case = self.cases["repeat_same_path"]
        first, repeated = case["expected"]["prefix_equivalent"]
        before = replay_case(case, self.policy, first)
        after = replay_case(case, self.policy, repeated)
        points = sample_box(case)
        np.testing.assert_allclose(
            actual_material_field(points, case, before),
            actual_material_field(points, case, after),
            rtol=0,
            atol=2e-15,
        )

    def test_crossing_path_union_is_order_independent(self):
        case = self.cases["tilted_crossing_paths"]
        replay = replay_case(case, self.policy)
        reversed_replay = dict(replay, primitives=list(reversed(replay["primitives"])))
        points = sample_box(case)
        np.testing.assert_array_equal(
            actual_material_field(points, case, replay),
            actual_material_field(points, case, reversed_replay),
        )

    def test_plan_boundary_does_not_hide_actual_overcut(self):
        case = self.cases["plan_edge_overcut"]
        replay = replay_case(case, self.policy)
        point = np.asarray([[3.5, 0.0, -0.1]])
        self.assertGreater(actual_material_field(point, case, replay)[0], 0)
        self.assertLess(planned_material_field(point, case, replay)[0], 0)
        self.assertEqual(classify_points(point, case, replay)[0], "outside_plan_removed")

    def test_stop_gap_and_late_event_do_not_create_missing_motion(self):
        case = self.cases["stop_gap_and_late_event"]
        replay = replay_case(case, self.policy)
        self.assertEqual(replay["late_event_ids"], ["g_late"])
        self.assertFalse(
            any(
                np.allclose(item["start"], [1.0, 0.0, 0.4])
                and np.allclose(item["end"], [3.0, 0.0, 0.4])
                for item in replay["primitives"]
            )
        )
        self.assertEqual(
            classify_points([[2.0, 0.0, -0.05]], case, replay)[0],
            "retained",
        )

    def test_ambiguous_or_invalid_record_is_rejected(self):
        document = deepcopy(self.document)
        document["coordinate_frame"]["length_unit"] = "m"
        with self.assertRaisesRegex(RecordError, "毫米"):
            validate_document(document)

        case = deepcopy(self.cases["stop_gap_and_late_event"])
        case["events"][3]["connect_from_previous"] = True
        with self.assertRaisesRegex(RecordError, "跨停钻"):
            replay_case(case, self.policy)

    def test_smooth_seam_ablation_uses_same_vertical_case(self):
        case = self.cases["vertical_depth_transition"]
        center_z = min(event["position_mm"][2] for event in case["events"])
        arguments = dict(
            center_z=center_z,
            tool_radius=case["tool"]["radius_mm"],
            clip_radius=case["plan"]["allowed_radius_mm"],
            outer_radius=3.0,
            spacing=0.25,
        )
        all_seams = audit_candidate(generate(**arguments, preserve_smooth_seam=True))
        source_aware = audit_candidate(generate(**arguments, preserve_smooth_seam=False))
        self.assertFalse(all_seams["accepted"])
        self.assertIn("shape_quality", all_seams["reasons"])
        self.assertTrue(source_aware["accepted"], source_aware)
        self.assertEqual(source_aware["bad_faces"], 0)
        self.assertGreater(source_aware["min_angle_deg"], 25)
        self.assertLessEqual(source_aware["mesh_to_target_upper_mm"], 0.1)
        self.assertLessEqual(source_aware["target_to_mesh_upper_mm"], 0.1)
        self.assertLess(
            abs(
                source_aware["target_to_mesh_upper_mm"]
                - all_seams["target_to_mesh_upper_mm"]
            ),
            1e-5,
        )

    def test_arbitrary_capsule_vertical_interval_matches_implicit_boundary(self):
        case = self.cases["tilted_crossing_paths"]
        replay = replay_case(case, self.policy)
        axis = np.linspace(-1.7, 1.7, 35)
        xy = np.stack(np.meshgrid(axis, axis, indexing="ij"), axis=-1).reshape(-1, 2)
        for primitive in replay["primitives"]:
            with self.subTest(event=primitive["event_id"]):
                lower, upper = capsule_vertical_interval(xy, primitive)
                intersects = np.isfinite(lower)
                self.assertTrue(np.any(intersects))
                lower_points = np.column_stack((xy[intersects], lower[intersects]))
                upper_points = np.column_stack((xy[intersects], upper[intersects]))

                np.testing.assert_allclose(
                    capsule_field(lower_points, primitive),
                    0.0,
                    rtol=0,
                    atol=5e-12,
                )
                below = lower_points.copy()
                below[:, 2] -= 1e-6
                above = upper_points.copy()
                above[:, 2] += 1e-6
                self.assertTrue(np.all(capsule_field(below, primitive) > 0))
                self.assertTrue(np.all(capsule_field(above, primitive) > 0))
                np.testing.assert_allclose(
                    capsule_field(upper_points, primitive),
                    0.0,
                    rtol=0,
                    atol=5e-12,
                )

    def test_tilted_crossing_height_candidate_has_no_hidden_cavity(self):
        case = self.cases["tilted_crossing_paths"]
        replay = replay_case(case, self.policy)
        dense_axis = np.linspace(-2.0, 2.0, 161)
        xy = np.stack(
            np.meshgrid(dense_axis, dense_axis, indexing="ij"),
            axis=-1,
        )
        _, _, diagnostics = top_connected_height(xy, case, replay)
        self.assertTrue(diagnostics["all_removed_intervals_top_connected"])
        self.assertEqual(diagnostics["internal_cavity_sample_count"], 0)

        mesh, mesh_diagnostics = height_surface(
            case,
            replay,
            (-2.0, 2.0, -2.0, 2.0),
            0.1,
        )
        self.assertTrue(mesh_diagnostics["all_removed_intervals_top_connected"])
        np.testing.assert_allclose(
            actual_material_field(mesh.points, case, replay),
            0.0,
            rtol=0,
            atol=5e-12,
        )

    def test_source_fitted_candidate_repairs_only_failed_development_cells(self):
        case = self.cases["tilted_crossing_paths"]
        replay = replay_case(case, self.policy)
        mesh, diagnostics = source_fitted_height_surface(
            case,
            replay,
            (-2.0, 2.0, -2.0, 2.0),
            0.1,
        )
        quality = mesh_quality(mesh)
        topology = mesh_topology(mesh)
        self.assertEqual(diagnostics["pre_alignment_bad_cells"], 2)
        self.assertEqual(diagnostics["snapped_vertex_count"], 3)
        self.assertEqual(diagnostics["inserted_midpoint_count"], 3)
        self.assertEqual(diagnostics["post_refinement_bad_cells"], 0)
        self.assertTrue(diagnostics["source_transition_continuous"])
        self.assertEqual(quality["bad_faces"], 0)
        self.assertGreaterEqual(quality["min_angle_deg"], 25.0)
        self.assertEqual(topology["self_intersection_faces"], 0)
        self.assertEqual(topology["non_manifold_edges"], 0)

    def test_source_fitted_candidate_leaves_passing_frozen_cases_unmodified(self):
        document = load_document(HERE / "method_evaluation_cases.json")
        for case in document["cases"]:
            with self.subTest(case=case["id"]):
                replay = replay_case(case, document["replay_policy"])
                raw, _ = height_surface(
                    case,
                    replay,
                    (-2.0, 2.0, -2.0, 2.0),
                    0.1,
                )
                fitted, diagnostics = source_fitted_height_surface(
                    case,
                    replay,
                    (-2.0, 2.0, -2.0, 2.0),
                    0.1,
                )
                self.assertEqual(diagnostics["pre_alignment_bad_cells"], 0)
                self.assertEqual(diagnostics["snapped_vertex_count"], 0)
                self.assertEqual(diagnostics["inserted_midpoint_count"], 0)
                np.testing.assert_array_equal(fitted.points, raw.points)
                np.testing.assert_array_equal(fitted.faces, raw.faces)

    def test_source_constrained_candidate_preserves_passing_frozen_cases(self):
        document = load_document(HERE / "method_evaluation_cases.json")
        for case in document["cases"]:
            with self.subTest(case=case["id"]):
                replay = replay_case(case, document["replay_policy"])
                raw, _ = height_surface(
                    case,
                    replay,
                    (-2.0, 2.0, -2.0, 2.0),
                    0.1,
                )
                constrained, diagnostics = source_constrained_height_surface(
                    case,
                    replay,
                    (-2.0, 2.0, -2.0, 2.0),
                    0.1,
                )
                self.assertTrue(diagnostics["height_graph_supported"])
                self.assertEqual(
                    diagnostics["optimized_constraint_point_count"],
                    0,
                )
                np.testing.assert_array_equal(constrained.points, raw.points)
                np.testing.assert_array_equal(constrained.faces, raw.faces)

    def test_frozen_v3_development_cases_define_continuity_boundary(self):
        document = load_document(HERE / "quality_development_cases_v3.json")
        self.assertTrue(document["screening"]["raw_only_screening"])
        self.assertTrue(
            document["screening"][
                "constrained_source_not_run_before_freeze"
            ]
        )
        self.assertEqual(
            document["screening"]["selected_generation_indices"],
            [24, 0, 123, 124, 282, 267, 391, 392],
        )

        supported = []
        accepted = []
        for case in document["cases"]:
            with self.subTest(case=case["id"]):
                replay = replay_case(case, document["replay_policy"])
                mesh, diagnostics = source_constrained_height_surface(
                    case,
                    replay,
                    (-2.0, 2.0, -2.0, 2.0),
                    0.1,
                )
                support = diagnostics["height_graph_supported"]
                quality = mesh_quality(mesh)
                topology = mesh_topology(mesh)
                supported.append(support)
                accepted.append(support and quality["bad_faces"] == 0)
                self.assertEqual(topology["non_manifold_edges"], 0)
                self.assertEqual(topology["inconsistent_interior_edges"], 0)
                self.assertEqual(topology["self_intersection_faces"], 0)
                np.testing.assert_allclose(
                    actual_material_field(mesh.points, case, replay),
                    0.0,
                    rtol=0,
                    atol=5e-12,
                )
                if support:
                    self.assertEqual(quality["bad_faces"], 0)
                    self.assertGreaterEqual(quality["min_angle_deg"], 25.0)
                    self.assertGreaterEqual(
                        diagnostics[
                            "normalized_minimum_quality_after_optimization"
                        ],
                        diagnostics[
                            "normalized_minimum_quality_before_optimization"
                        ],
                    )
                else:
                    self.assertGreater(
                        diagnostics[
                            "global_discontinuous_source_transition_count"
                        ],
                        0,
                    )
                    self.assertIn(
                        "垂直壁",
                        diagnostics["constraint_rejection_reason"],
                    )

        self.assertEqual(
            supported,
            [True, True, True, True, True, True, False, True],
        )
        self.assertEqual(
            accepted,
            [True, True, True, True, True, True, False, True],
        )

    def test_geogram_adapter_removes_only_contained_motion_primitives(self):
        case = self.cases["tilted_crossing_paths"]
        replay = replay_case(case, self.policy)
        primitives, removed = effective_primitives(replay["primitives"])
        self.assertEqual(
            [primitive["event_id"] for primitive in primitives],
            ["x1", "y1"],
        )
        self.assertEqual(removed, ["x0", "y0"])

    def test_planned_state_metrics_match_fixed_volume_answers(self):
        keys = [
            "planned_removal_volume_mm3",
            "achieved_within_plan_volume_mm3",
            "remaining_within_plan_volume_mm3",
            "overcut_within_plan_volume_mm3",
            "outside_plan_removed_volume_mm3",
            "actual_removed_volume_mm3",
            "completion_fraction",
        ]
        rows = {}
        for case_id in [
            "shallow_milling",
            "repeat_same_path",
            "plan_edge_overcut",
            "vertical_depth_transition",
        ]:
            case = self.cases[case_id]
            replay = replay_case(case, self.policy)
            actual = planned_state_metrics(case, replay)
            expected = case["expected"]["state_metrics"]
            tolerance = expected["absolute_tolerance_mm3"]
            for key in keys:
                with self.subTest(case=case_id, metric=key):
                    self.assertAlmostEqual(
                        actual[key],
                        expected[key],
                        delta=tolerance,
                    )
            self.assertLessEqual(actual["completion_fraction"], 1.0)
            rows[case_id] = actual

        for key in keys:
            self.assertAlmostEqual(
                rows["shallow_milling"][key],
                rows["repeat_same_path"][key],
                delta=1e-12,
            )
        self.assertGreater(
            rows["plan_edge_overcut"]["outside_plan_removed_volume_mm3"],
            0.0,
        )
        self.assertGreater(
            rows["vertical_depth_transition"][
                "overcut_within_plan_volume_mm3"
            ],
            0.0,
        )

    def test_frozen_method_evaluation_cases_are_valid_and_in_scope(self):
        document = load_document(HERE / "method_evaluation_cases.json")
        self.assertEqual(len(document["cases"]), 3)
        self.assertTrue(all(case["split"] == "evaluation" for case in document["cases"]))
        for case in document["cases"]:
            with self.subTest(case=case["id"]):
                replay = replay_case(case, document["replay_policy"])
                axis = np.linspace(-2.0, 2.0, 81)
                xy = np.stack(
                    np.meshgrid(axis, axis, indexing="ij"),
                    axis=-1,
                )
                _, _, diagnostics = top_connected_height(xy, case, replay)
                self.assertTrue(
                    diagnostics["all_removed_intervals_top_connected"],
                    diagnostics,
                )
                if "repeat_equivalent_event_ids" in case:
                    before_id, after_id = case["repeat_equivalent_event_ids"]
                    before = replay_case(case, document["replay_policy"], before_id)
                    after = replay_case(case, document["replay_policy"], after_id)
                    points = sample_box(case)
                    np.testing.assert_allclose(
                        actual_material_field(points, case, before),
                        actual_material_field(points, case, after),
                        rtol=0,
                        atol=2e-15,
                    )

    def test_frozen_raw_quality_failures_and_unseen_source_fitting_result(self):
        document = load_document(HERE / "quality_failure_cases_v2.json")
        self.assertTrue(document["screening"]["raw_only_screening"])
        self.assertTrue(
            document["screening"]["source_fitted_not_run_before_freeze"]
        )
        self.assertEqual(
            document["screening"]["selected_generation_indices"],
            [15, 132, 247, 356],
        )

        fitted_bad_faces = []
        continuous_transitions = []
        for case in document["cases"]:
            with self.subTest(case=case["id"]):
                replay = replay_case(case, document["replay_policy"])
                raw, diagnostics = height_surface(
                    case,
                    replay,
                    (-2.0, 2.0, -2.0, 2.0),
                    0.1,
                )
                raw_quality = mesh_quality(raw)
                expected = case["expected_raw_quality"]
                self.assertEqual(raw_quality["vertices"], expected["vertices"])
                self.assertEqual(raw_quality["faces"], expected["faces"])
                self.assertEqual(raw_quality["bad_faces"], expected["bad_faces"])
                self.assertAlmostEqual(raw_quality["min_q"], expected["min_q"])
                self.assertAlmostEqual(
                    raw_quality["min_angle_deg"],
                    expected["min_angle_deg"],
                )
                self.assertEqual(
                    diagnostics["all_removed_intervals_top_connected"],
                    expected["all_removed_intervals_top_connected"],
                )
                dense_axis = np.linspace(-2.0, 2.0, 161)
                dense_xy = np.stack(
                    np.meshgrid(dense_axis, dense_axis, indexing="ij"),
                    axis=-1,
                )
                _, _, dense_diagnostics = top_connected_height(
                    dense_xy,
                    case,
                    replay,
                )
                self.assertEqual(
                    dense_diagnostics["internal_cavity_sample_count"],
                    expected["dense_scope_internal_cavity_samples"],
                )

                fitted, fitted_diagnostics = source_fitted_height_surface(
                    case,
                    replay,
                    (-2.0, 2.0, -2.0, 2.0),
                    0.1,
                )
                fitted_bad_faces.append(mesh_quality(fitted)["bad_faces"])
                continuous_transitions.append(
                    fitted_diagnostics["source_transition_continuous"]
                )
                topology = mesh_topology(fitted)
                self.assertEqual(topology["non_manifold_edges"], 0)
                self.assertEqual(topology["inconsistent_interior_edges"], 0)
                self.assertEqual(topology["self_intersection_faces"], 0)

        self.assertEqual(fitted_bad_faces, [0, 4, 3, 5])
        self.assertEqual(continuous_transitions, [True, True, True, False])


if __name__ == "__main__":
    unittest.main()
