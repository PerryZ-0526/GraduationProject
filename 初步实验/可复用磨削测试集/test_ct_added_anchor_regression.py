"""原失败、仅掩码更新和完整能量重算的同输入实际GPU对照资产。"""
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent/"CT第十事件追加固定锚点回归_v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class AddedAnchorRegressionTests(unittest.TestCase):
    def test_all_frozen_hashes(self):
        files = read(ROOT/"01-冻结清单.json")["files"]
        self.assertEqual(len(files), 36)
        for item in files:
            self.assertEqual(digest(ROOT/item["file"]), item["sha256"])

    def test_same_projection_input_and_distinct_energy_outcomes(self):
        for method in ("boolean", "expanded"):
            expected = digest(ROOT/"original"/method/"before_projection.obj")
            for variant in ("mask_only", "complete_energy"):
                self.assertEqual(digest(ROOT/variant/method/"before_projection.obj"), expected)
            original = read(ROOT/"original"/method/"diff_trace.json")["rows"]
            mask_only = read(ROOT/"mask_only"/method/"diff_trace.json")["rows"]
            complete = read(ROOT/"complete_energy"/method/"diff_trace.json")["rows"]
            self.assertFalse(original[0]["full_energy_finite"])
            self.assertFalse(mask_only[0]["full_energy_finite"])
            self.assertTrue(all(x["finite"] for x in mask_only[0]["component_energies"]))
            self.assertEqual(mask_only[0]["collision_contacts"]["nonpositive_or_nonfinite"], 0)
            self.assertEqual(len(complete), 50)
            self.assertTrue(all(x["full_energy_finite"] and not x["nonfinite_free_vertices"] for x in complete))

    def test_added_anchors_and_saved_output_binding(self):
        source = trimesh.load(ROOT/"source.obj", process=False)
        record = read(ROOT/"complete_energy_record.json")
        for method, row in zip(("boolean", "expanded"), record["rows"]):
            folder = ROOT/"complete_energy"/method
            anchor = read(folder/"anchor_updates.json")
            self.assertEqual(anchor["current_anchor_count"]-anchor["initial_anchor_count"], 3)
            self.assertTrue(anchor["updates"][0]["encoded_initial_exact"])
            self.assertTrue(anchor["updates"][0]["full_energy_recomputed"])
            self.assertTrue(anchor["updates"][0]["recomputed_energy_finite"])
            certificate = row["output_metrics"]["full_exact_embedding"]
            self.assertTrue(certificate["embedded_closed"])
            self.assertEqual(certificate["saved_sha256"], digest(folder/"candidate.obj"))
            self.assertTrue(row["same_before_projection_as_failed_baseline"])
            mesh = trimesh.load(folder/"candidate.obj", process=False)
            ids = np.asarray(row["vertex_original_ids"])
            original = ids >= 0
            np.testing.assert_array_equal(mesh.vertices[original], source.vertices[ids[original]])

    def test_actual_independent_reference_probe_budget(self):
        rows = read(ROOT/"02-独立参照几何补查.json")["rows"]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertLessEqual(row["geometry"]["probe_max_mm"], .1)
            self.assertFalse(row["geometry"]["continuous_geometry_certified"])


if __name__ == "__main__":
    unittest.main()
