"""验证间歇反馈执行器对真实失败帧的成本记录。"""
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
import run_cadence_feedback as runner


class FailureCosts(unittest.TestCase):
    def test_cleanup_failure_is_timed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'inputs').mkdir()
            parent=root/'parent.obj';parent.write_text('parent')
            (root/'inputs'/'tool.obj').write_text('tool')
            engine=SimpleNamespace(difference=lambda *args: (_ for _ in ()).throw(ValueError('真实清理拒绝')))
            row,new_parent=runner.step(engine,SimpleNamespace(prepared=root),{'id':'route'},
                {'mesh':'tool.obj','event_id':'e0'},parent,{},'every',root,'step',False,None)
            self.assertEqual(row['status'],'common_cleanup_rejected')
            self.assertGreater(row['frame_wall_ms'],0)
            self.assertIsNone(new_parent)
            self.assertIn('+08:00',row['time_beijing'])

    def test_geogram_failure_is_timed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'inputs').mkdir()
            parent=root/'parent.obj';parent.write_text('parent')
            (root/'inputs'/'tool.obj').write_text('tool')
            engine=SimpleNamespace(difference=lambda *args:(None,{'returncode':1}))
            row,new_parent=runner.step(engine,SimpleNamespace(prepared=root),{'id':'route'},
                {'mesh':'tool.obj','event_id':'e0'},parent,{},'every',root,'step',False,None)
            self.assertEqual(row['status'],'geogram_failed')
            self.assertGreater(row['frame_wall_ms'],0)
            self.assertIsNone(new_parent)


if __name__=='__main__':unittest.main()
