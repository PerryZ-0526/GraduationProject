"""实际GPU完整投影与拒绝控制的冻结证据，不能替代连续反馈验收。"""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parent/"原固定几何完整投影与CCD回归_v1"


def read(name):
    return json.loads((ROOT/"inputs"/name).read_text(encoding="utf-8"))


class PreservedProjectionTests(unittest.TestCase):
    def test_all_frozen_files(self):
        manifest = json.loads((ROOT/"01-原固定几何投影回归清单.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["published"])
        self.assertEqual(len(manifest["files"]),26)
        for row in manifest["files"]:
            content = (ROOT/row["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(),row["sha256"])
            self.assertEqual(len(content),row["bytes"])

    def test_full_energy_and_derivatives(self):
        record = read("projection_record.json")
        self.assertFalse(record["published"])
        self.assertEqual(len(record["rows"]),2)
        for row in record["rows"]:
            self.assertTrue(row["numerical_diagnostic"]["passed"])
            self.assertEqual(row["numerical_diagnostic"]["diff_calls"],50)
        for name in ("boolean_trace.json","expanded_trace.json"):
            rows = read(name)["rows"]
            self.assertEqual(len(rows),50)
            self.assertTrue(all(row["full_energy_finite"] and row["finite_positions"]
                                and not row["nonfinite_free_vertices"] for row in rows))
            self.assertEqual(rows[0]["collision_contacts"]["nonpositive_or_nonfinite"],0)

    def test_static_and_mixed_motion_controls(self):
        result = read("controls.json")
        self.assertTrue(result["passed"])
        self.assertEqual(read("controls_execution.json")["execution"]["returncode"],0)
        positive = result["positive_fixed"]
        self.assertEqual(positive["failure_flags"],[0,0])
        self.assertTrue(positive["energy_finite"] and positive["constrained_gradient_zero"]
                        and positive["constrained_hessian_zero"] and positive["cached_derivatives_zero"])
        self.assertLessEqual(positive["energy_relative_error"],1e-5)
        self.assertEqual(result["true_zero_flags"],[8,0])
        self.assertEqual(result["nonzero_fixed_velocity_flags"],[0,1])
        self.assertTrue(all(result["mixed_contact_exact_array_equal"]))
        self.assertTrue(result["mixed_finite"])
        self.assertGreater(result["mixed_ccd_step"],0)
        self.assertLess(result["mixed_ccd_step"],1)

    def test_actual_compiled_source_binding(self):
        binding = read("01-实际编译分支绑定.json")
        self.assertEqual(len(binding["rows"]),2)
        for row in binding["rows"]:
            self.assertTrue(row["transform_matches"])
            for kind in ("original","modified"):
                path = ROOT/"inputs"/row[kind]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),row[kind+"_sha256"])

    def test_embedding_and_conditional_input(self):
        embedding = read("embedding_record.json")
        self.assertEqual(len(embedding["tests"]),6)
        self.assertTrue(all(row["passed"] for row in embedding["tests"]))
        rows = embedding["rows"]
        self.assertEqual(len(rows),3)
        self.assertTrue(all(row["embedded_closed"] for row in rows))
        hashes = {hashlib.sha256((ROOT/"inputs"/name).read_bytes()).hexdigest()
                  for name in ("boolean_candidate.obj","expanded_candidate.obj","repaired_candidate.obj")}
        self.assertEqual(hashes,{row["sha256"] for row in rows})
        repair = read("repair_record.json")["repair"]
        self.assertTrue(repair["accepted_for_fixed_geometry_backend"])
        self.assertTrue(repair["requires_full_embedding_before_gpu"])
        self.assertEqual(repair["remaining_arithmetic_invalid_faces"],6)
        self.assertEqual(repair["remaining_fp64_threshold_faces"],0)


if __name__ == "__main__":
    unittest.main()
