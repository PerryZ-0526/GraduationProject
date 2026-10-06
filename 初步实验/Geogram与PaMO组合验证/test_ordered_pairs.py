"""三源三轮四方法计划必须完整、确定且使用两种真实工作器。"""
import unittest
from run_ordered_pairs import METHODS, PairEngines, schedule
from run_ordered_features import FeatureEngines


class OrderedPairTests(unittest.TestCase):
    def test_complete_declared_schedule(self):
        ids=('thin','sphere','curved')
        tasks=schedule(ids)
        expected={(case,round_id,method) for case in ids for round_id in range(3) for method in METHODS}
        self.assertEqual(len(tasks),36)
        self.assertEqual(set(tasks),expected)

    def test_repeatable_shuffle_without_case_selection(self):
        ids=('thin','sphere','curved')
        self.assertEqual(schedule(ids),schedule(ids))
        self.assertNotEqual(schedule(ids),sorted(schedule(ids)))

    def test_same_worker_dispatch_and_audit_as_features(self):
        self.assertIs(PairEngines.run,FeatureEngines.run)
        self.assertIs(PairEngines.audit,FeatureEngines.audit)

    def test_saved_recheck_keeps_physical_and_fixed_contracts(self):
        from pathlib import Path
        import recheck_ordered_features
        from recheck_ordered_pairs import build_pair_recheck
        source=build_pair_recheck(Path(recheck_ordered_features.__file__).read_text(encoding='utf-8'))
        compile(source,'pair_recheck','exec')
        for marker in ('mesh_valid_saved_binding(mesh,certificates)',"geometry['probe_max_mm']<=.1",
            'check_initial_encoding_record', 'fixed_surface_contract', "row['same_input_sha256']",
            "row['artifact_directory']", "r['round']", "range(3)"):
            self.assertIn(marker,source)
        self.assertNotIn('feature_width_mm',source)
        self.assertNotIn('tools[case]',source)


if __name__=='__main__':
    unittest.main()
