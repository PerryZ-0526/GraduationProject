import math
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "CUDA真实骨面对照"))
from coverage_inputs import original_plan
from clipped_patch import (
    Rejected,
    audit_candidate,
    cumulative_center,
    exact_distance,
    generate,
    target_profile,
)


class ClippedPatchTests(unittest.TestCase):
    def test_original_plan_vertical_segments_use_clipped_features(self):
        vertical = [
            item
            for item in original_plan()
            if item["start"][:2] == item["end"][:2]
            and item["start"][2] != item["end"][2]
        ]
        self.assertEqual([item["step"] for item in vertical], [135, 136, 137, 138])
        centers = []
        for item in vertical:
            centers.extend([item["start"][2], item["end"][2]])
            candidate = generate(
                center_z=cumulative_center(centers),
                tool_radius=item["radius"],
                clip_radius=item["clip_radius"],
            )
            self.assertTrue(candidate.profile.clip_active)
            self.assertEqual(
                set(candidate.feature_rings),
                {"sphere_plan_clip", "plan_clip_plane"},
            )

    def test_actual_plan_clip_creates_two_true_feature_rings(self):
        candidate = generate(
            center_z=-1.0,
            tool_radius=2.9,
            clip_radius=2.5,
            outer_radius=4.0,
        )
        self.assertTrue(candidate.profile.clip_active)
        self.assertEqual(candidate.profile.wall_kind, "plan_clip")
        self.assertEqual(
            set(candidate.feature_rings),
            {"sphere_plan_clip", "plan_clip_plane"},
        )
        self.assertGreater(candidate.profile.features[0]["angle_deg"], 25.0)

    def test_smooth_sweep_seam_is_not_forced(self):
        candidate = generate(
            center_z=-1.0,
            tool_radius=2.0,
            clip_radius=3.0,
            outer_radius=4.0,
        )
        self.assertFalse(candidate.profile.clip_active)
        self.assertEqual(candidate.profile.wall_kind, "sweep_cylinder")
        self.assertNotIn("sphere_sweep_cylinder", candidate.feature_rings)
        self.assertIn("sweep_cylinder_plane", candidate.feature_rings)

    def test_clip_activation_tangency_has_no_zero_width_wall(self):
        radius, clip = 2.9, 2.5
        center = math.sqrt(radius**2 - clip**2)
        profile = target_profile(center, radius, clip, 4.0)
        self.assertFalse(profile.clip_active)
        self.assertIsNone(profile.wall_kind)
        self.assertAlmostEqual(profile.mouth_radius, clip, places=12)

    def test_no_contact_is_rejected(self):
        with self.assertRaisesRegex(Rejected, "无接触或相切"):
            generate(center_z=2.9, tool_radius=2.9, clip_radius=2.5)

    def test_repeated_and_reordered_centers_define_same_target(self):
        a = cumulative_center([0.5, -1.0, -1.0, -2.5])
        b = cumulative_center([-2.5, 0.5, -1.0])
        self.assertEqual(a, -2.5)
        self.assertEqual(a, b)
        first = generate(a)
        second = generate(b)
        np.testing.assert_array_equal(first.mesh.vertices, second.mesh.vertices)
        np.testing.assert_array_equal(first.mesh.faces, second.mesh.faces)

    def test_exact_distance_covers_all_surface_sources(self):
        profile = target_profile(-1.0)
        sphere_bottom = [0.0, 0.0, profile.center_z - profile.tool_radius]
        wall_middle = [
            profile.mouth_radius,
            0.0,
            profile.wall_bottom_z / 2,
        ]
        plane_middle = [
            (profile.mouth_radius + profile.outer_radius) / 2,
            0.0,
            0.0,
        ]
        distances = exact_distance(
            [sphere_bottom, wall_middle, plane_middle, [0.0, 0.0, sphere_bottom[2] - 0.1]],
            profile,
        )
        np.testing.assert_allclose(distances, [0.0, 0.0, 0.0, 0.1], atol=1e-12)

    def test_actual_plan_candidate_passes_complete_audit(self):
        candidate = generate(center_z=-1.0, spacing=0.25)
        audit = audit_candidate(candidate)
        self.assertTrue(audit["accepted"], audit)
        self.assertEqual(audit["bad_faces"], 0)
        self.assertEqual(audit["self_intersection_faces"], 0)
        self.assertTrue(audit["one_boundary_loop"])
        self.assertTrue(audit["outer_boundary_ok"])
        self.assertLessEqual(audit["mesh_to_target_upper_mm"], 0.1)
        self.assertLessEqual(audit["target_to_mesh_upper_mm"], 0.1)

    def test_near_tangent_thin_feature_is_rejected_by_quality(self):
        radius, clip = 2.9, 2.5
        activation = math.sqrt(radius**2 - clip**2)
        candidate = generate(
            center_z=activation - 1e-4,
            tool_radius=radius,
            clip_radius=clip,
            spacing=0.25,
        )
        audit = audit_candidate(candidate)
        self.assertFalse(audit["accepted"])
        self.assertIn("shape_quality", audit["reasons"])


if __name__ == "__main__":
    unittest.main()
