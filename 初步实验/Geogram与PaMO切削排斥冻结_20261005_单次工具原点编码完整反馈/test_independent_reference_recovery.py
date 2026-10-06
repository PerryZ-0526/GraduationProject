"""参照修复的拓扑及原表面误差预算负例。"""
import unittest
from unittest.mock import patch,MagicMock
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import numpy as np
import trimesh
from independent_reference_recovery import validate_replayed_reference,recover_reference
from locality_masks import save_obj_fp64
from audit_followup_candidate import sha256


class IndependentReferenceRecoveryTests(unittest.TestCase):
    def test_closed_identity_passes(self):
        mesh=trimesh.creation.box()
        result,record=validate_replayed_reference(mesh)
        self.assertIsNotNone(result)
        self.assertTrue(record["accepted"])

    def test_open_surface_rejected(self):
        mesh=trimesh.Trimesh([[0,0,0],[1,0,0],[0,1,0]],[[0,1,2]],process=False)
        result,record=validate_replayed_reference(mesh)
        self.assertIsNone(result)
        self.assertFalse(record["accepted"])

    def test_duplicate_faces_record_rejection(self):
        box=trimesh.creation.box()
        duplicate=trimesh.util.concatenate([box,box])
        result,record=validate_replayed_reference(duplicate)
        self.assertIsNone(result)
        self.assertEqual(record["status"],"reference_cleanup_rejected")
        self.assertIn("重复面",record["error"])

    def test_distant_legal_mesh_not_a_reference(self):
        mesh=trimesh.creation.box()
        moved=mesh.copy();moved.apply_translation([1,0,0])
        with patch("independent_reference_recovery.repair_input",return_value=(moved,np.ones(len(moved.faces)),{"accepted":True})):
            result,record=validate_replayed_reference(mesh)
        self.assertIsNone(result)
        self.assertGreater(record["raw_to_repaired_geometry"]["probe_max_mm"],1e-7)

    def test_contained_reuse_preserves_saved_hash(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);prior=root/"prior.obj";folder=root/"current";folder.mkdir()
            save_obj_fp64(trimesh.creation.box(),prior)
            engine=SimpleNamespace(independent_reference_cache={"r":(prior,sha256(prior),{})})
            result,record=recover_reference(engine,root,{"id":"r"},"e8",None,folder,True)
            self.assertTrue(record["accepted"])
            self.assertTrue(result.is_watertight)
            self.assertEqual(sha256(folder/"validated_reference.obj"),sha256(prior))

    def test_corrupt_cache_rejected(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);prior=root/"prior.obj";prior.write_text("modified")
            engine=SimpleNamespace(independent_reference_cache={"r":(prior,"wrong",{})})
            with self.assertRaises(ValueError):
                recover_reference(engine,root,{"id":"r"},"e8",None,root,True)

    def test_failed_new_cut_invalidates_old_reference(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);inputs=root/"inputs";inputs.mkdir()
            initial=inputs/"initial.obj";initial.write_text("initial")
            tool=inputs/"tool.obj";tool.write_text("tool")
            route={"id":"r","initial_mesh":initial.name,"initial_mesh_sha256":sha256(initial),
                "prefix_tools":[{"event_id":"e0","mesh":tool.name,"sha256":sha256(tool)}]}
            engine=SimpleNamespace(independent_reference_cache={"r":(initial,sha256(initial),{})},
                sftp=MagicMock(),client=None,remote="/isolated")
            # 远端重放失败后也不能把旧缓存交给后续包含事件。
            with patch("independent_reference_recovery.execute",return_value={"returncode":1}),patch("independent_reference_recovery.retrieve"):
                result,record=recover_reference(engine,root,route,"e0",None,root,False)
            self.assertIsNone(result)
            self.assertFalse(record["accepted"])
            self.assertNotIn("r",engine.independent_reference_cache)


if __name__=="__main__":
    unittest.main()
