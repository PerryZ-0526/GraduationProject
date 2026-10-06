"""新固定后端的门控不能篡改FP32计数，且拒绝真实退化和不可信来源。"""
import ast
from pathlib import Path
import tempfile
import numpy as np
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import trimesh
from preserved_feedback_gate import check_preserved_mesh,backend_methods,clean_for_backend
from preserved_controller_source import build_controller,build_reference
from exact_embedding_gate import stored_mesh_sha256
from preserved_geometry_precondition import require_fixed_degenerate_faces

HERE = Path(__file__).parent


class PreservedFeedbackTests(unittest.TestCase):
    def test_generated_controller_retains_state_and_fp32_branch(self):
        source = (HERE/"run_constrained_feedback.py").read_text(encoding="utf-8")
        changed = build_controller(source)
        ast.parse(changed)
        self.assertIn('branch == "full" and input_metrics["fp32_zero_area_faces"]',changed)
        self.assertIn('methods = backend_methods(branch, labels_valid)',changed)
        # 回灌、版本与拒绝状态代码逐行保留，不能因换后端跳过失败事件。
        for marker in ('parent_paths[branch] = accepted','versions[branch] += 1',
                       'blocked[branch] = True','row["status"] = "all_registered_attempts_rejected"'):
            self.assertEqual(source.count(marker),changed.count(marker))
        reference = build_reference((HERE/"independent_reference_recovery.py").read_text(encoding="utf-8"))
        ast.parse(reference)
        self.assertIn('prefix_tools_through(route,event)',reference)
        self.assertIn('initial_sha256=sha256(initial)',reference)

    def test_untrusted_labels_no_unsupported_full_fallback(self):
        self.assertEqual(backend_methods("full",False),("full",))
        self.assertEqual(backend_methods("candidate",True),("boolean","expanded"))
        self.assertEqual(backend_methods("candidate",False),())

    def test_full_gate_keeps_original_fp32_count(self):
        mesh = trimesh.creation.box()
        digest = stored_mesh_sha256(mesh)
        certificate = dict(saved_sha256=digest,embedded_closed=True)
        engine = SimpleNamespace(preserved_embedding_cache={digest:certificate})
        metrics = dict(finite=True,zero_area_faces=0,fp32_zero_area_faces=6,watertight=True,
                       winding_consistent=True,vertex_manifold_closed=True,self_intersection_faces=201)
        with tempfile.TemporaryDirectory() as tmp,patch("preserved_feedback_gate.mesh_valid",return_value=(False,metrics)):
            valid,result = check_preserved_mesh(engine,Path(tmp),mesh,"source")
        self.assertTrue(valid)
        self.assertEqual(result["fp32_zero_area_faces"],6)
        self.assertEqual(result["historical_unresolved_alarm_faces"],201)
        self.assertTrue(result["full_exact_embedding_bound"])

    def test_cached_invalid_embedding_rejected(self):
        mesh = trimesh.creation.box()
        digest = stored_mesh_sha256(mesh)
        engine = SimpleNamespace(preserved_embedding_cache={digest:dict(saved_sha256=digest,embedded_closed=False)})
        with tempfile.TemporaryDirectory() as tmp:
            valid,_ = check_preserved_mesh(engine,Path(tmp),mesh,"source")
        self.assertFalse(valid)

    def test_original_branch_uses_original_cleanup(self):
        with patch("preserved_feedback_gate.pair_repair",return_value=(1,2,3)) as original:
            self.assertEqual(clean_for_backend("mesh","labels","full"),(1,2,3))
            original.assert_called_once_with("mesh","labels")

    def test_wrong_cached_digest_rejected(self):
        mesh = trimesh.creation.box()
        digest = stored_mesh_sha256(mesh)
        engine = SimpleNamespace(preserved_embedding_cache={digest:dict(saved_sha256="different",embedded_closed=True)})
        with tempfile.TemporaryDirectory() as tmp:
            valid,_ = check_preserved_mesh(engine,Path(tmp),mesh,"source")
        self.assertFalse(valid)

    def test_actual_gpu_worker_guard(self):
        vertices = np.array([[10,0,0],[10+1e-8,0,0],[10,1,0]])
        faces = np.array([[0,1,2]])
        fixed = np.ones(3,bool)
        self.assertEqual(require_fixed_degenerate_faces(vertices,faces,fixed,1.0,np.zeros(3))["encoded_degenerate_faces"],1)
        fixed[1] = False
        with self.assertRaises(ValueError):
            require_fixed_degenerate_faces(vertices,faces,fixed,1.0,np.zeros(3))


if __name__ == "__main__":
    unittest.main()
