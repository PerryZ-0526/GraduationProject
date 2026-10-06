import hashlib
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
FREEZE = HERE / "source_constrained_v3_freeze.json"
EVALUATION = (
    HERE
    / "实验结果"
    / "20260918_011811_source_constrained_v3_evaluation"
    / "results.json"
)
SCOPE_AUDIT = (
    HERE
    / "实验结果"
    / "20260918_012936_non_single_value_scope"
    / "results.json"
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SourceConstrainedV3FreezeTests(unittest.TestCase):
    def test_frozen_core_and_unseen_evaluation_result(self):
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        for name, expected in freeze["core_sha256"].items():
            self.assertEqual(sha256(HERE / name), expected, name)

        result = json.loads(EVALUATION.read_text(encoding="utf-8"))
        self.assertEqual(result["core_sha256"], freeze["core_sha256"])
        self.assertEqual(
            result["input_document_sha256"],
            freeze["core_sha256"]["quality_failure_cases_v2.json"],
        )
        self.assertEqual(
            result["summary"],
            {
                "cases_completed": 4,
                "case_count": 4,
                "height_graph_supported": 3,
                "accepted": 3,
                "legacy_v2_accepted_by_quality_and_continuity": 1,
            },
        )
        rows = result["cases"]
        self.assertEqual(
            [
                row["source_constrained_v3"]["quality"]["bad_faces"]
                for row in rows
            ],
            [0, 0, 0, 5],
        )
        self.assertEqual(
            [
                row["source_constrained_v3"]["diagnostics"][
                    "height_graph_supported"
                ]
                for row in rows
            ],
            [True, True, True, False],
        )
        self.assertEqual(
            [
                row["source_constrained_v3"]["accepted_for_this_case"]
                for row in rows
            ],
            [True, True, True, False],
        )
        self.assertGreater(
            rows[-1]["source_constrained_v3"]["diagnostics"][
                "global_source_transition_max_one_sided_jump_mm"
            ],
            0.04,
        )

    def test_finer_scope_audit_exposes_grid_sampling_false_negatives(self):
        result = json.loads(SCOPE_AUDIT.read_text(encoding="utf-8"))
        self.assertEqual(result["summary"]["case_count"], 4)
        self.assertEqual(result["summary"]["missed_at_0_025_mm"], 4)
        self.assertEqual(
            [
                row["first_tested_spacing_with_detection_mm"]
                for row in result["cases"]
            ],
            [0.005, 0.00625, 0.0125, 0.0125],
        )
        for row in result["cases"]:
            self.assertEqual(
                row["checks"][0]["internal_cavity_sample_count"],
                0,
            )
            self.assertTrue(
                any(
                    check["internal_cavity_sample_count"] > 0
                    for check in row["checks"][1:]
                )
            )


if __name__ == "__main__":
    unittest.main()
