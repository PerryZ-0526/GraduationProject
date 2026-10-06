"""保留评价冻结必须拒绝开发运行中记录和缺失分母。"""
import json
from pathlib import Path
import tempfile
import unittest
from freeze_ordered_evaluation import freeze
from freeze_ordered_evaluation import runtime_sources,observed_candidate_parameters


class EvaluationFreezeTests(unittest.TestCase):
    def test_identical_released_entry_can_be_reused_without_rewrite(self):
        from run_frozen_ordered_evaluation import release_or_verify_entry
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'released.py'
            source='# 中文生成入口\nprint(1)\n'
            release_or_verify_entry(path,source)
            before=path.read_bytes();stamp=path.stat().st_mtime_ns
            release_or_verify_entry(path,source)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(path.stat().st_mtime_ns,stamp)

    def test_changed_released_entry_is_rejected_without_overwrite(self):
        from run_frozen_ordered_evaluation import release_or_verify_entry
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'released.py'
            path.write_bytes(b'original')
            with self.assertRaisesRegex(ValueError,'冻结版本不符'):
                release_or_verify_entry(path,'changed\n')
            self.assertEqual(path.read_bytes(),b'original')

    def test_actual_triangle_parameters_are_distinct_from_legacy_cgal_label(self):
        attempt=dict(method='planar_tangent_protected_preserved_geometry_areaguard_shared',triangle_options='pYYq20S128Q',max_regions=200)
        record=dict(parameters=dict(iterations=3),rows=[dict(attempts=[attempt,attempt,dict(method='full')])])
        observed=observed_candidate_parameters(record)
        self.assertEqual(len(observed),1)
        self.assertEqual(observed[0]['parameters'],dict(triangle_options='pYYq20S128Q',max_regions=200))
        self.assertNotIn('iterations',observed[0]['parameters'])

    def test_dependency_closure_includes_existing_sibling_audit_module(self):
        with tempfile.TemporaryDirectory() as name:
            parent=Path(name);root=parent/'combo';root.mkdir()
            shared=parent/'共同运动记录与方法对照';shared.mkdir()
            (root/'entry.py').write_text('import audit_shared\n',encoding='utf-8')
            (shared/'audit_shared.py').write_text('import math\n',encoding='utf-8')
            self.assertEqual(runtime_sources(root,['entry.py']),['audit_shared.py','entry.py'])

    def test_released_entry_checks_generated_worker_before_continuation(self):
        from run_frozen_ordered_evaluation import build_bound_entry,expected_generated_sources
        expected=expected_generated_sources(dict(actual_environment={},method_files=[
            dict(file='方法副本/'+name,sha256='a'*64) for name in ('initial_encoding_worker.py','planar_patch.py','preserved_reference.py')]))
        source='class Engine:\n    def setup(self):\n        info=super().setup()\n        return info\n'
        built=build_bound_entry(source,expected)
        compile(built,'release','exec')
        self.assertLess(built.index('sha256(self.output/name)'),built.index('return info'))
        self.assertIn('initial_encoding_worker.py',built)

    def test_runtime_dependency_closure_includes_dynamic_source_files(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            (root/'entry.py').write_text('from helper import run\nsource="worker.py"\n',encoding='utf-8')
            (root/'helper.py').write_text('import nested\n',encoding='utf-8')
            (root/'nested.py').write_text('import helper\n',encoding='utf-8')
            (root/'worker.py').write_text('source="kernel.cpp"\n',encoding='utf-8')
            (root/'kernel.cpp').write_text('// 中文测试夹具\n',encoding='utf-8')
            self.assertEqual(runtime_sources(root,['entry.py']),['entry.py','helper.py','kernel.cpp','nested.py','worker.py'])

    def test_running_development_cannot_release_evaluation(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);development=root/'dev';development.mkdir()
            (development/'01-反馈执行与独立审计.json').write_text(json.dumps(dict(status='running')),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'尚未终态'):
                freeze(development,root/'missing',root/'result')
            self.assertFalse((root/'result').exists())

    def test_incomplete_manifest_cannot_reduce_denominator(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);development=root/'dev';development.mkdir();prepared=root/'prepared';prepared.mkdir()
            (development/'01-反馈执行与独立审计.json').write_text(json.dumps(dict(status='completed_with_recorded_failures')),encoding='utf-8')
            (prepared/'01-完整范围冻结清单.json').write_text(json.dumps(dict(routes=[])),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'完整分母'):
                freeze(development,prepared,root/'result')
            self.assertFalse((root/'result').exists())

    def test_complete_actual_sources_and_sixty_inputs_are_frozen(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);development=root/'dev';development.mkdir();prepared=root/'prepared';prepared.mkdir()
            inputs=prepared/'inputs';inputs.mkdir()
            from audit_followup_candidate import sha256
            routes=[]
            for index in range(12):
                paths=[]
                for part in range(5):
                    path=inputs/(str(index)+'_'+str(part)+'.obj');path.write_text(str((index,part)),encoding='utf-8');paths.append(path)
                routes.append(dict(id=str(index),split='evaluation',cutting_prefix_ids=['e0','e1','e2','e3'],
                    initial_mesh=paths[0].name,initial_mesh_sha256=sha256(paths[0]),
                    prefix_tools=[dict(mesh=p.name,sha256=sha256(p)) for p in paths[1:]]))
            (development/'01-反馈执行与独立审计.json').write_text(json.dumps(dict(status='completed_with_recorded_failures',environment={})),encoding='utf-8')
            (prepared/'01-完整范围冻结清单.json').write_text(json.dumps(dict(routes=routes)),encoding='utf-8')
            for filename in ('initial_encoding_worker.py','planar_patch.py','ordered_physical_cleanup.py','ordered_physical_cleanup_snapshot.py'):
                (development/filename).write_text('# 中文冻结夹具\n',encoding='utf-8')
            (development/'preserved_reference.py').write_text('from ordered_physical_cleanup import ordered_cancel_opposed as clean_cancel_opposed\n'
                '# prefix_tools_through(route, event)\n# sha256(initial) != route["initial_mesh_sha256"]\n# sha256(source) != tool["sha256"]\n',encoding='utf-8')
            result=freeze(development,prepared,root/'result')
            self.assertEqual(len(result['inputs']),60)
            self.assertEqual(result['planned_events'],48)
            self.assertEqual(len(result['method_files']),5)
            self.assertFalse(result['evaluation_results_opened'])
            from run_frozen_ordered_evaluation import verify_freeze
            self.assertEqual(verify_freeze(root/'result',prepared)['planned_events'],48)
            for row in result['method_files']:
                self.assertEqual(sha256(root/'result'/row['file']),row['sha256'])
            # 此夹具只验证冻结与摘要，不把文本对象当作有效网格。
            paths[0].write_text('已改变输入',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'冻结评价输入变化'):
                verify_freeze(root/'result',prepared)
            with self.assertRaisesRegex(ValueError,'冻结输入变化'):
                freeze(development,prepared,root/'changed_result')
            self.assertFalse((root/'changed_result').exists())


if __name__=='__main__':
    unittest.main()
