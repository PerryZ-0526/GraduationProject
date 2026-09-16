"""真实Qt/VTK回归：网格刷新不能改写用户相机，显式重置仍有效。"""
import unittest
import numpy as np
from PyQt6 import QtWidgets
from PyQt6.QtTest import QTest
from research_viewer import ResearchViewer
from real_bone_interactive_app import InteractiveApp


def camera_state(camera):
    return np.array([*camera.position, *camera.focal_point, *camera.up,
                     camera.parallel_scale, camera.view_angle, float(camera.parallel_projection)])


class CameraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_playback_modes_and_rejected_state(self):
        window = ResearchViewer()
        window.show()
        self.qt.processEvents()
        try:
            for projection in [False, True]:
                branch = window.branches.findText('真实局部 / shift_x_1 / cuda')
                self.assertGreaterEqual(branch, 0, '回归所需的CUDA序列必须存在')
                window.branches.setCurrentIndex(branch)
                window.slider.setValue(0)
                camera = window.plotter.camera
                # 鼠标交互直接改变VTK相机；不能用会设置PyVista相机标志的属性setter替代。
                camera.SetPosition(11., -17., 9.)
                camera.SetFocalPoint(1.1, .4, -.3)
                camera.SetViewUp(.2, .5, 1.)
                camera.SetParallelProjection(projection)
                camera.SetParallelScale(2.7)
                camera.SetViewAngle(23.)
                expected = camera_state(camera)
                window.advance()
                self.assertEqual(window.slider.value(), 1)
                np.testing.assert_allclose(camera_state(window.plotter.camera), expected, rtol=0, atol=1e-12)
                window.toggle_play()
                QTest.qWait(450)
                self.assertGreater(window.slider.value(), 1, '定时播放必须实际推进状态')
                if window.timer.isActive():
                    window.toggle_play()
                np.testing.assert_allclose(camera_state(window.plotter.camera), expected, rtol=0, atol=1e-12)
                for mode in range(3):
                    window.mode.setCurrentIndex(mode)
                    self.qt.processEvents()
                    np.testing.assert_allclose(camera_state(window.plotter.camera), expected, rtol=0, atol=1e-12)
                window.slider.setValue(window.slider.maximum())
                window.slider.setValue(0)
                np.testing.assert_allclose(camera_state(window.plotter.camera), expected, rtol=0, atol=1e-12)
                window.plotter.reset_camera()
                self.assertFalse(np.allclose(camera_state(window.plotter.camera), expected))
        finally:
            window.close()

    def test_online_step(self):
        window = InteractiveApp()
        window.show()
        self.qt.processEvents()
        try:
            camera = window.plotter.camera
            camera.SetPosition(110., -170., 90.)
            camera.SetFocalPoint(11., 4., -3.)
            camera.SetViewUp(.2, .5, 1.)
            camera.SetParallelScale(27.)
            expected = camera_state(camera)
            window.single_step()
            np.testing.assert_allclose(camera_state(window.plotter.camera), expected, rtol=0, atol=1e-12)
        finally:
            window.close()


if __name__ == '__main__':
    unittest.main()
