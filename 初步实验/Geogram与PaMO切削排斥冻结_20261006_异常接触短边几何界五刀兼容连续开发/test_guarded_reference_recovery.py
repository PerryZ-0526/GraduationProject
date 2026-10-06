"""逐步参照的缓存一致性、失败停止与上传父链回归。"""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import trimesh
from audit_followup_candidate import sha256
from guarded_reference_recovery import recover_reference
from locality_masks import save_obj_fp64


class GuardedReferenceTests(unittest.TestCase):
    def test_contained_reuse_keeps_saved_object(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior = root/"prior.obj"
            save_obj_fp64(trimesh.creation.box(), prior)
            engine = SimpleNamespace(guarded_reference_cache={"r": (prior, sha256(prior), {})})
            mesh, row = recover_reference(engine, root, {"id": "r"}, "e2", None, root/"reuse", True)
            self.assertTrue(row["accepted"])
            self.assertTrue(mesh.is_watertight)
            self.assertEqual(sha256(root/"reuse/validated_reference.obj"), sha256(prior))
            self.assertEqual(row["runs"], [])

    def test_corrupt_cache_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior = root/"prior.obj"
            prior.write_text("changed", encoding="utf-8")
            engine = SimpleNamespace(guarded_reference_cache={"r": (prior, "wrong", {})})
            with self.assertRaises(ValueError):
                recover_reference(engine, root, {"id": "r"}, "e2", None, root/"reuse", True)

    def run_new_cut(self, failed_boolean=False, failed_check=False):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root/"inputs"
            inputs.mkdir()
            initial = inputs/"initial.obj"
            save_obj_fp64(trimesh.creation.box(), initial)
            tool = inputs/"tool.obj"
            save_obj_fp64(trimesh.creation.box(), tool)
            route = dict(id="r", initial_mesh=initial.name, initial_mesh_sha256=sha256(initial),
                prefix_tools=[dict(event_id="e"+str(i), mesh=tool.name, sha256=sha256(tool)) for i in range(2)])
            uploaded = {}
            sftp = MagicMock()
            sftp.put.side_effect = lambda local, remote: uploaded.update({remote: Path(local).read_bytes()})
            engine = SimpleNamespace(guarded_reference_cache={"r": (initial, sha256(initial), {})},
                sftp=sftp, client=None, remote="/isolated")
            calls = []

            def execute(client, argv, *args, **kwargs):
                if argv[0] == "sha256sum":
                    import hashlib
                    return dict(returncode=0, stdout=hashlib.sha256(uploaded[argv[1]]).hexdigest()+" file")
                calls.append(argv)
                return dict(returncode=int(failed_boolean), stdout="")

            def retrieve(client, transfer, remote, local):
                if str(local).endswith(".obj"):
                    save_obj_fp64(trimesh.creation.box(), local)
                else:
                    local.write_text("log", encoding="utf-8")

            checks = [(True, {}), (not failed_check, {}), (True, {})]
            with patch("guarded_reference_recovery.execute", side_effect=execute), \
                    patch("guarded_reference_recovery.retrieve", side_effect=retrieve), \
                    patch("guarded_reference_recovery.check_preserved_mesh", side_effect=checks):
                mesh, row = recover_reference(engine, root, route, "e1", None, root/"output", False)
            return mesh, row, calls, dict(engine.guarded_reference_cache)

    def test_boolean_failure_stops_and_clears_cache(self):
        mesh, row, calls, cache = self.run_new_cut(failed_boolean=True)
        self.assertIsNone(mesh)
        self.assertEqual(row["status"], "guarded_replay_boolean_failed")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("r", cache)

    def test_invalid_intermediate_stops_next_boolean(self):
        mesh, row, calls, cache = self.run_new_cut(failed_check=True)
        self.assertIsNone(mesh)
        self.assertEqual(row["status"], "guarded_replay_intermediate_rejected")
        self.assertEqual(len(calls), 1)
        self.assertFalse(row["steps"][0]["accepted"])
        self.assertNotIn("r", cache)

    def test_excessive_repair_distance_stops_next_boolean(self):
        # 合法嵌入不足以接受参照，超出修复距离预算仍应停止并清空缓存。
        with patch("guarded_reference_recovery.global_geometry", return_value={"probe_max_mm": 1e-3}):
            mesh, row, calls, cache = self.run_new_cut()
        self.assertIsNone(mesh)
        self.assertEqual(row["status"], "guarded_replay_intermediate_rejected")
        self.assertEqual(len(calls), 1)
        self.assertGreater(row["steps"][0]["raw_to_repaired_geometry"]["probe_max_mm"], 1e-7)
        self.assertNotIn("r", cache)

    def test_next_boolean_uses_checked_independent_parent(self):
        mesh, row, calls, cache = self.run_new_cut()
        self.assertIsNotNone(mesh)
        self.assertTrue(row["accepted"])
        self.assertEqual(row["tool_events"], ["e0", "e1"])
        self.assertEqual(calls[0][1], "/isolated/r_e1_guarded_initial.obj")
        self.assertEqual(calls[1][1], "/isolated/r_e1_guarded_after_e0.obj")
        self.assertEqual(len(row["steps"]), 2)
        self.assertIn("r", cache)


if __name__ == "__main__":
    unittest.main()
