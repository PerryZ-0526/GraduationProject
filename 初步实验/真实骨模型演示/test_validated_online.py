"""在线入口验收：全序列对既有实验、真实拒绝、整骨复核拒绝及实际窗口。"""
import unittest
from unittest.mock import patch
from pathlib import Path
import json
import time
import numpy as np
from validated_online import ValidatedSession, create_window, HERE
from real_patch import local_trajectory


class SessionTests(unittest.TestCase):
    def test_default_entry_and_explicit_legacy(self):
        import real_bone_interactive_app as entry
        with patch('sys.argv', ['app']), patch('validated_online.run') as run:
            entry.main()
            run.assert_called_once()
        with patch('sys.argv', ['app', '--legacy-bool']), patch.object(entry, 'run_gui') as legacy:
            entry.main()
            legacy.assert_called_once()

    def test_full_sequence_matches_saved_experiment(self):
        session = ValidatedSession()
        result = session.advance()
        self.assertEqual(result[1]['step'], 0)
        while not session.finished:
            result = session.advance()
            self.assertTrue(result[1]['accepted'])
            self.assertGreaterEqual(result[1]['min_angle_deg'], 25)
            self.assertGreaterEqual(result[1]['min_q'], .4)
            self.assertLessEqual(result[1]['error_bound_mm'], .1)
        self.assertEqual(session.step, 16)
        saved = np.load(HERE.parent / '局部适用域与核显计算/实验结果/local_1.8.npz')
        for actual, expected in zip(session.snapshots, saved['snapshots']):
            # 不同CPU架构允许远低于几何预算的末位舍入差异，不放宽任何验收阈值。
            np.testing.assert_allclose(
                actual[session.candidate['mapping']], expected, rtol=0, atol=1e-12)
        self.assertEqual(len(session.snapshots), len(saved['snapshots']))
        self.assertIsNone(session.advance())

    def test_rejection_does_not_publish(self):
        session = ValidatedSession(trajectory=[local_trajectory(1.8)[0], local_trajectory(0.)[0]])
        session.advance()
        whole, _ = session.advance()
        before = whole.vertices.copy()
        mesh, row = session.advance()
        self.assertIsNone(mesh)
        self.assertFalse(row['accepted'])
        self.assertEqual(session.step, 1)
        self.assertTrue(session.finished)
        np.testing.assert_array_equal(session.snapshots[-1], before)

    def test_whole_audit_rejection_rolls_back(self):
        session = ValidatedSession()
        session.advance()
        initial = session.snapshots[-1].copy()
        # 初态已独立验收；只在本步整骨复核注入拒绝，检查发布门控而非放宽几何规则。
        with patch('dynamic.resolve_flags', side_effect=lambda candidate, audit: audit.update(accepted=False)):
            mesh, row = session.advance()
        self.assertIsNone(mesh)
        self.assertFalse(row['accepted'])
        self.assertEqual(session.step, 0)
        np.testing.assert_array_equal(session.snapshots[-1], initial)

    def test_actual_gui_playback_and_camera(self):
        from PyQt6 import QtWidgets
        from PyQt6.QtTest import QTest
        qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = create_window()
        # 自动化期间隔离真实鼠标输入；仍直接改变VTK相机并验证实际定时刷新，避免人工拖动污染断言。
        window.plotter.interactor.setEnabled(False)
        window.show()
        def wait_until(predicate):
            limit = time.monotonic() + 90
            while not predicate():
                QTest.qWait(30)
                if time.monotonic() > limit:
                    self.fail(window.status.text())
        try:
            wait_until(lambda: window.future is None)
            self.assertIsNotNone(window.mesh, window.status.text())
            camera = window.plotter.camera
            camera.Azimuth(17)
            camera.Elevation(8)
            camera.Zoom(1.2)
            expected = np.array(list(window.plotter.camera_position), dtype=float)
            zoom = camera.parallel_scale
            window.single_step()
            pending = window.future
            window.single_step()
            self.assertIs(window.future, pending, '忙时不能重复提交候选')
            window.toggle_play()
            window.toggle_play()
            wait_until(lambda: window.future is None)
            self.assertEqual(window.session.step, 1, '暂停后不能自动继续推进')
            window.toggle_play()
            wait_until(lambda: window.session.finished and window.future is None)
            self.assertEqual(window.session.step, 16, window.status.text())
            np.testing.assert_allclose(list(window.plotter.camera_position), expected, rtol=0, atol=1e-12)
            self.assertEqual(window.plotter.camera.parallel_scale, zoom)
            window.mode.setCurrentIndex(1)
            np.testing.assert_allclose(list(window.plotter.camera_position), expected, rtol=0, atol=1e-12)
            window.mode.setCurrentIndex(0)
            qt.processEvents()
            window.export()
            output = sorted((HERE / '在线逐步验收输出').iterdir())[-1]
            window.grab().save(str(output / '窗口验证.png'))
            records = json.loads((output / 'records.json').read_text(encoding='utf-8'))
            self.assertEqual(len(records), 17)
            print('GUI_EVIDENCE', output, flush=True)
            self.assertTrue((output / 'metadata.json').exists())
            window.restart()
            wait_until(lambda: window.future is None)
            before = window.mesh.vertices.copy()
            # 使用真实适用域负例触发窗口拒绝状态，不替换验收函数。
            window.session.trajectory[0] = local_trajectory(0.)[0]
            window.single_step()
            wait_until(lambda: window.future is None)
            self.assertIn('拒绝', window.status.text())
            self.assertEqual(window.session.step, 0)
            self.assertFalse(window.play_button.isEnabled())
            np.testing.assert_array_equal(window.mesh.vertices, before)
        finally:
            wait_until(lambda: window.future is None)
            window.close()
            qt.processEvents()


if __name__ == '__main__':
    unittest.main()
