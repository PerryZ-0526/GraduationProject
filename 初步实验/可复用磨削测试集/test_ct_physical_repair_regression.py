"""CT物理退化失败、修复和完整投影必须绑定同一冻结对象。"""
import hashlib
import json
from pathlib import Path
import unittest
import trimesh

ROOT = Path(__file__).resolve().parent/"CT第十四事件物理面积与投影回归_v1"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PhysicalRepairRegressionTests(unittest.TestCase):
    def test_frozen_objects(self):
        files = read(ROOT/"01-冻结清单.json")["files"]
        self.assertEqual(len(files), 35)
        for item in files:
            self.assertEqual(digest(ROOT/item["file"]), item["sha256"])

    def test_original_failure_and_encoding_defects_remain_visible(self):
        failure = read(ROOT/"original_candidate_failure.json")
        self.assertEqual(failure["status"], "maintenance_input_invalid")
        self.assertEqual(failure["input_metrics"]["zero_area_faces"], 5)
        for role, source in (("physical_source", "raw_candidate.obj"), ("physical_reference", "raw_reference.obj")):
            record = read(ROOT/role/"01-物理面积判据隔离诊断.json")
            self.assertEqual(record["source_sha256"], digest(ROOT/"inputs"/source))
            self.assertEqual(record["metrics"]["zero_area_faces"], 0)
            self.assertGreater(record["metrics"]["fp32_zero_area_faces"], 0)
            self.assertLessEqual(record["geometry"]["probe_max_mm"], 1e-7)
            self.assertFalse(record["published"])
            mesh = trimesh.load(ROOT/role/"candidate.obj", process=False)
            self.assertTrue((mesh.area_faces > 1e-12).all())

    def test_same_repair_object_and_exact_embedding(self):
        record = read(ROOT/"01-全网格精确嵌入审计.json")
        self.assertTrue(all(row["passed"] for row in record["tests"]))
        expected = {digest(ROOT/role/"candidate.obj") for role in ("physical_source", "physical_reference")}
        self.assertEqual({row["sha256"] for row in record["rows"]}, expected)
        self.assertTrue(all(row["embedded_closed"] for row in record["rows"]))
        agreement = read(ROOT/"02-正式入口与隔离对象一致性.json")
        self.assertTrue(all(row["accepted"] and row["same_saved_object"] for row in agreement["rows"]))

    def test_full_projection_and_independent_probe(self):
        record = read(ROOT/"projection_record.json")
        self.assertEqual(record["status"], "completed_with_recorded_outcomes")
        self.assertFalse(record["published"])
        self.assertEqual(len(record["rows"]), 2)
        for method, row in zip(("boolean", "expanded"), record["rows"]):
            self.assertEqual(row["status"], "accepted_sampled")
            self.assertTrue(row["numerical_diagnostic"]["passed"])
            self.assertEqual(row["numerical_diagnostic"]["finite_energy_calls"], 50)
            certificate = row["output_metrics"]["full_exact_embedding"]
            self.assertTrue(certificate["embedded_closed"])
            self.assertEqual(certificate["saved_sha256"], digest(ROOT/"projection"/method/"candidate.obj"))
        for row in read(ROOT/"02-独立参照几何补查.json")["rows"]:
            self.assertLessEqual(row["geometry"]["probe_max_mm"], .1)
            self.assertFalse(row["geometry"]["continuous_geometry_certified"])


if __name__ == "__main__":
    unittest.main()
