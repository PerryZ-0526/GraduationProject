"""验证失败分母与空变化域统计，避免未执行或无材料变化被记成收益。"""

import unittest

from summarize_constrained_validation import distributions


class StatisticsTests(unittest.TestCase):
    def test_blocked_frames_keep_denominator_without_zero_metrics(self):
        result = distributions([{"status": "blocked_by_previous_failure"}])
        self.assertEqual(result["planned_records_present"], 1)
        self.assertEqual(result["published_frames"], 0)
        self.assertIsNone(result["worst_probe_error_mm"])
        self.assertIsNone(result["median_frame_wall_including_audit_ms"])

    def test_empty_region_has_no_small_angle_or_quality_denominator(self):
        quality = {"total_faces": 0, "high_quality_25_deg_q_0_4": {"fraction": None, "area_fraction": None}}
        quality.update({f"angle_below_{a}_deg": {"fraction": None, "area_fraction": None} for a in (10, 5, 1)})
        row = {"status": "published_under_sampled_and_vertex_protocol", "selected_method": "boolean",
            "frame_wall_including_audit_ms": 1, "signed_removed_volume_mm3": 0,
            "cumulative_geometry": {"probe_max_mm": 0}, "preservation": {"uncut_sampled_max_mm": 0,
                "quality_all": quality, "quality_sweep_margin_roi": quality}}
        result = distributions([row])
        self.assertEqual(result["published_zero_nominal_removal_frames"], 1)
        self.assertEqual(result["quality_sweep_margin_roi"]["nonempty_region_frames"], 0)
        self.assertIsNone(result["quality_sweep_margin_roi"]["angle_statistics"]["10"]["median_face_percent"])


if __name__ == "__main__":
    unittest.main()
