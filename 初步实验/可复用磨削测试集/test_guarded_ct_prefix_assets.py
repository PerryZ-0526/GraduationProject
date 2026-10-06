"""核对实际十二步参照对象、原工具身份及完整嵌入保存绑定。"""
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
ROOT = HERE/"CT独立参照十二工具逐步重放_v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class GuardedCTPrefixAssets(unittest.TestCase):
    def test_all_62_frozen_files(self):
        manifest = read(ROOT/"01-冻结清单.json")
        self.assertEqual(len(manifest["files"]), 62)
        for item in manifest["files"]:
            self.assertEqual(digest(ROOT/item["file"]), item["sha256"])

    def test_original_initial_and_exact_tool_prefix(self):
        original_path = HERE/"真实CT既有两路线输入_v1/01-完整范围冻结清单.json"
        manifest = read(ROOT/"01-冻结清单.json")
        self.assertEqual(digest(original_path), manifest["original_manifest_sha256"])
        original = next(r for r in read(original_path)["routes"] if r["id"] == manifest["route"])
        record = read(ROOT/"replay_record.json")["record"]
        self.assertEqual(digest(ROOT/"initial.obj"), original["initial_mesh_sha256"])
        self.assertEqual(record["initial_sha256"], original["initial_mesh_sha256"])
        self.assertEqual(manifest["events"], ["e"+str(i) for i in range(12)])
        self.assertEqual(record["tool_events"], manifest["events"])
        for i, tool in enumerate(original["prefix_tools"][:12]):
            self.assertEqual(digest(ROOT/tool["event_id"]/"tool.obj"), tool["sha256"])
            self.assertEqual(record["tool_sha256"][i], tool["sha256"])

    def test_all_saved_repaired_objects_bind_exact_checks(self):
        record = read(ROOT/"replay_record.json")["record"]
        self.assertTrue(record["accepted"])
        for step in record["steps"]:
            folder = ROOT/step["event"]
            self.assertEqual(digest(folder/"raw.obj"), step["raw_sha256"])
            saved_sha = digest(folder/"repaired.obj")
            self.assertEqual(saved_sha, step["saved_sha256"])
            cert = read(folder/"embedding_audit.json")["metrics"]["full_exact_embedding"]
            self.assertEqual(cert["saved_sha256"], saved_sha)
            self.assertTrue(cert["embedded_closed"])
            self.assertEqual(cert["execution"]["returncode"], 0)
            self.assertEqual(cert["self_intersection_pairs"], 0)
            mesh = trimesh.load(folder/"repaired.obj", process=False)
            self.assertTrue(np.isfinite(mesh.vertices).all())
            self.assertTrue(mesh.is_watertight)
            self.assertTrue(mesh.is_winding_consistent)
            self.assertTrue((mesh.area_faces > 1e-12).all())

    def test_all_steps_preserve_declared_repair_budget(self):
        record = read(ROOT/"replay_record.json")["record"]
        self.assertEqual(len(record["steps"]), 12)
        self.assertFalse(record["continuous_geometry_certified"])
        for step in record["steps"]:
            self.assertTrue(step["accepted"])
            self.assertLessEqual(step["raw_to_repaired_geometry"]["probe_max_mm"], 1e-7)


if __name__ == "__main__":
    unittest.main()
