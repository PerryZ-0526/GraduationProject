"""候选发布外部契约与原版分支独立，回退也不能绕过外部保持。"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import trimesh
from run_active_patch_feedback import ActiveReferenceEngine,audit_active_candidate
from run_active_patch_projection import ActivePatchEngine


class ActiveFeedbackTests(unittest.TestCase):
    def test_comparison_baseline_all_vertex_probe_can_reject_sampled_acceptance(self):
        from active_patch_comparisons import ActiveFeatureEngines
        import run_ordered_features as features
        engine=ActiveFeatureEngines.__new__(ActiveFeatureEngines)
        row=dict(feature_method='full',execution=dict(returncode=0),status='accepted_sampled')
        with patch.object(features.FeatureEngines,'audit',return_value=row),patch('active_patch_comparisons.trimesh.load',return_value=trimesh.creation.box()),patch('active_patch_comparisons.global_geometry',return_value=dict(probe_max_mm=.12)):
            result=engine.audit('source.obj',None,None,'folder',row)
        self.assertEqual(result['baseline_sampled_audit_status'],'accepted_sampled')
        self.assertEqual(result['status'],'all_vertex_geometry_budget_rejected')

    def test_comparison_all_vertex_probe_does_not_overwrite_existing_rejection(self):
        from active_patch_comparisons import ActiveFeatureEngines
        import run_ordered_features as features
        engine=ActiveFeatureEngines.__new__(ActiveFeatureEngines)
        row=dict(feature_method='global',execution=dict(returncode=0),status='full_embedding_rejected')
        with patch.object(features.FeatureEngines,'audit',return_value=row),patch('active_patch_comparisons.trimesh.load',return_value=trimesh.creation.box()),patch('active_patch_comparisons.global_geometry',return_value=dict(probe_max_mm=0)):
            result=engine.audit('source.obj',None,None,'folder',row)
        self.assertEqual(result['status'],'full_embedding_rejected')

    def test_feature_entry_snapshot_exists_before_shared_setup(self):
        from active_patch_comparisons import ActiveFeatureEngines
        import run_ordered_features as features
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);output=root/'output';output.mkdir()
            entry=root/'entry.py';entry.write_text('# 实际小特征入口夹具\n',encoding='utf-8')
            (output/'01-小特征浅磨工具冻结.json').write_text('{}',encoding='utf-8')
            engine=ActiveFeatureEngines.__new__(ActiveFeatureEngines);engine.output=output;engine.entry_path=entry
            def shared_setup():
                self.assertEqual((output/'ordered_features_snapshot.py').read_bytes(),entry.read_bytes())
                return {}
            with patch.object(features.FeatureEngines,'setup',side_effect=shared_setup):
                engine.setup()

    def test_feature_recheck_keeps_all_methods_and_relative_width(self):
        from pathlib import Path
        import recheck_ordered_features
        from recheck_active_patch_features import build_recheck
        source=build_recheck(Path(recheck_ordered_features.__file__).read_text(encoding='utf-8'))
        compile(source,'active_feature_saved','exec')
        for marker in ("manifest['negative_inputs']", "('full','global','spatial','boolean')",
            "external['passed']",'geometry_to_feature_width_ratio','mesh_valid_saved_binding'):
            self.assertIn(marker,source)

    def test_fair_pairs_candidate_recheck_keeps_external_contract(self):
        from pathlib import Path
        import recheck_ordered_features
        from recheck_active_patch_pairs import build_active_pair_recheck
        source=build_active_pair_recheck(Path(recheck_ordered_features.__file__).read_text(encoding='utf-8'))
        compile(source,'active_pair_saved','exec')
        for marker in ('len(actual)!=len(expected)',"r['round']",'range(3)',
            "external['passed']", "saved['rings']==2",'check_initial_encoding_record'):
            self.assertIn(marker,source)

    def test_actual_worker_dispatch_uses_active_generation(self):
        self.assertIs(ActiveReferenceEngine.run,ActivePatchEngine.run)

    def test_original_full_branch_keeps_original_protocol(self):
        row=dict(method='full',execution=dict(returncode=0),status='accepted_sampled')
        with patch('run_active_patch_feedback.audit_preserved_candidate',return_value=row),patch('run_active_patch_feedback.trimesh.load',side_effect=AssertionError('不应读取候选外部契约')):
            result=audit_active_candidate(None,None,None,None,'r_e0_full_full',row)
        self.assertEqual(result['status'],'accepted_sampled')
        self.assertNotIn('original_activity_external_face_contract',result)

    def test_candidate_and_full_fallback_cannot_delete_external_geometry(self):
        source=trimesh.creation.box();output=source.copy();output.vertices[0]+=.01
        with tempfile.TemporaryDirectory() as name:
            labels=Path(name)/'labels.json';labels.write_text(json.dumps(dict(operand_bits=[1]*len(source.faces))),encoding='utf-8')
            for method,folder in (('planar_tangent_active_scope_shared','r_e0_candidate_boolean'),('full','r_e0_candidate_full')):
                row=dict(method=method,execution=dict(returncode=0),status='accepted_sampled')
                with patch('run_active_patch_feedback.audit_preserved_candidate',return_value=row),patch('run_active_patch_feedback.trimesh.load',side_effect=[source,output]):
                    result=audit_active_candidate(None,'source.obj',None,labels,folder,row)
                self.assertEqual(result['status'],'original_activity_external_face_contract_rejected')
                self.assertFalse(result['original_activity_external_face_contract']['passed'])

    def test_unchanged_external_faces_survive_face_order_change(self):
        source=trimesh.creation.box();output=source.copy();output.faces=output.faces[::-1]
        with tempfile.TemporaryDirectory() as name:
            labels=Path(name)/'labels.json';labels.write_text(json.dumps(dict(operand_bits=[1]*len(source.faces))),encoding='utf-8')
            row=dict(method='planar_tangent_active_scope_shared',execution=dict(returncode=0),status='accepted_sampled')
            with patch('run_active_patch_feedback.audit_preserved_candidate',return_value=row),patch('run_active_patch_feedback.trimesh.load',side_effect=[source,output]):
                result=audit_active_candidate(None,'source.obj',None,labels,'r_e0_candidate_boolean',row)
            self.assertEqual(result['status'],'accepted_sampled')
            self.assertTrue(result['original_activity_external_face_contract']['passed'])


if __name__=='__main__':
    unittest.main()
