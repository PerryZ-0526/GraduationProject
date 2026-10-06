"""三项消融只改登记机制，去投影不保留执行CCD的分支。"""
from pathlib import Path
import unittest
from run_active_patch_ablation import build_variant
from recheck_active_patch_ablation import require_complete,no_projection_identity


class ActiveAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 使用主仓生成流程的实际源码模板，测试不连接GPU。
        cls.source=(Path(__file__).resolve().parent/'run_planar_worker.py').read_text(encoding='utf-8')

    def test_complete_identity(self):
        self.assertEqual(build_variant(self.source,'complete'),self.source)

    def test_unknown_variant_rejected(self):
        with self.assertRaises(ValueError):
            build_variant(self.source,'unknown')

    def test_no_band_changes_only_rings(self):
        source=build_variant(self.source,'without_transition_band')
        self.assertIn('"boolean", 0, allow_shared=shared)',source)
        self.assertIn('fixed = ids >= 0',source)
        self.assertIn('project_on_planes(source, mesh, fixed',source)

    def test_no_fixed_keeps_projection_and_records_residual_constraints(self):
        source=build_variant(self.source,'without_external_fixed')
        self.assertNotIn('fixed = ids >= 0',source)
        self.assertNotIn('fixed[np.unique(mesh.faces[outside_faces])] = True',source)
        self.assertIn('project_on_planes(source, mesh, fixed',source)

    def test_no_projection_has_no_ccd_call(self):
        source=build_variant(self.source,'without_projection')
        self.assertNotIn('result, projection =',source)
        self.assertIn('disabled_for_ablation',source)
        self.assertIn('fixed = ids >= 0',source)
        self.assertIn('before_projection.obj',source)

    def test_recheck_requires_all_36_unique_terminal_tasks(self):
        from run_active_patch_ablation import VARIANTS
        tasks=[(case,round_id,variant) for case in ('a','b','c') for round_id in range(3) for variant in VARIANTS]
        record=dict(status='completed_with_recorded_outcomes',schedule=tasks,
            rows=[dict(case=c,round=r,variant=v) for c,r,v in tasks])
        require_complete(record)
        for changed in (dict(record,status='running'),dict(record,rows=record['rows'][:-1]),
            dict(record,rows=record['rows'][:-1]+[record['rows'][0]])):
            with self.assertRaises(ValueError):
                require_complete(changed)

    def test_no_projection_placeholder_is_not_a_certificate(self):
        row=dict(author_projection_executed=False,projection='disabled_for_ablation')
        self.assertTrue(no_projection_identity(row))
        self.assertTrue(no_projection_identity(dict(row,numerical_diagnostic=dict(passed=False,trace_available=False))))
        self.assertFalse(no_projection_identity(dict(row,numerical_diagnostic=dict(passed=True,trace_available=True))))
        self.assertFalse(no_projection_identity(dict(row,author_projection_executed=True)))


if __name__=='__main__':
    unittest.main()
