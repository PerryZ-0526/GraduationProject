"""小特征四方法使用真实不同工作器，原前提与完整精确门控保留。"""
import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import trimesh
import run_ordered_features as features
from locality_masks import save_obj_fp64


class OrderedFeatureTests(unittest.TestCase):
    def test_four_methods_and_common_source_preconditions(self):
        source = features.build_feature_source()
        ast.parse(source)
        self.assertEqual(source.count('("full", "global", "spatial", "boolean")'), 2)
        self.assertIn("clean_for_backend(source, bits, 'candidate')", source)
        self.assertIn('method != "boolean" and checks["fp32_zero_area_faces"]', source)
        self.assertIn('engine.audit(source_path, tool, labels_path, destination, row)', source)

    def test_worker_routing_is_not_a_method_rename(self):
        engine = features.FeatureEngines.__new__(features.FeatureEngines)
        engine.baseline, engine.candidate = Mock(), Mock()
        engine.baseline.run.return_value = {}
        engine.candidate.run.return_value = {}
        for method in ('full', 'global', 'spatial', 'boolean'):
            row = engine.run('source', 'labels', 'tool', method, 'folder')
            self.assertEqual(row['feature_method'], method)
        self.assertEqual(engine.baseline.run.call_count, 3)
        engine.candidate.run.assert_called_once_with('source', 'labels', 'tool', 'boolean', 'folder')

    def test_failed_execution_cannot_gain_embedding_certificate(self):
        engine = features.FeatureEngines.__new__(features.FeatureEngines)
        engine.baseline = Mock()
        row = dict(feature_method='global', execution=dict(returncode=1), status='execution_failed')
        with patch.object(features, 'audit_candidate', return_value=row), patch.object(features, 'check_preserved_mesh') as exact:
            result = engine.audit('source', 'tool', 'labels', 'folder', row)
            self.assertEqual(result['status'], 'execution_failed')
            exact.assert_not_called()

    def test_baseline_output_still_requires_full_embedding(self):
        engine = features.FeatureEngines.__new__(features.FeatureEngines)
        engine.baseline = Mock()
        row = dict(feature_method='full', execution=dict(returncode=0), status='accepted_sampled', output_metrics={})
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            save_obj_fp64(trimesh.creation.box(), folder/'candidate.obj')
            with patch.object(features, 'audit_candidate', return_value=row), \
                 patch.object(features, 'check_preserved_mesh', return_value=(False, {})):
                self.assertEqual(engine.audit('source', 'tool', 'labels', folder, row)['status'], 'full_embedding_rejected')


if __name__ == '__main__':
    unittest.main()
