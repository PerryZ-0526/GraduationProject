"""逐步质量门控演示窗口；显示已发布状态与计算滞后。"""
from concurrent.futures import ThreadPoolExecutor

from PyQt6 import QtCore, QtWidgets

from dynamic_quality import DynamicQualityEngine, QualityRejected
from real_bone_interactive_app import InteractiveApp


class DynamicWindow(InteractiveApp):
    """每次只允许一个候选在后台计算，验收通过后才刷新窗口。"""

    def __init__(self):
        super().__init__(engine_factory=DynamicQualityEngine)
        self.window.setWindowTitle('逐步质量维护实验：尚未达到实时目标')
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.poll = QtCore.QTimer()
        self.poll.setInterval(30)
        self.poll.timeout.connect(self.finish_step)
        self.optimize_button.hide()
        self.compare_button.hide()
        self.quality_label.setMinimumHeight(90)
        self.quality_label.setText('每步局部维护并回灌；仅显示已验收网格')

    def single_step(self):
        if self.future is not None:
            return
        if self.engine.blocked:
            self.stop_playback()
            return
        self.sidebar.setEnabled(False)
        self.quality_label.setText(f'正在计算第{self.engine.step_index+1}步；画面仍为上一已验收状态')
        self.future = self.executor.submit(self.engine.step)
        self.poll.start()

    def finish_step(self):
        if self.future is None or not self.future.done():
            return
        self.poll.stop()
        try:
            row = self.future.result()
            if row is None:
                self.stop_playback()
                return
            self._refresh_scene()
            row['render_ms'] = self.last_render_ms
            self._update_metrics(row)
            self.quality_label.setText(
                f"已验收第{row['step']}步；差面{row['quality_bad_pct']:.3f}%\n"
                f"更新{row['pipeline_ms']:.0f} ms；"
                + ('超过100 ms目标' if row['deadline_missed'] else '本步未超时'))
        except QualityRejected:
            self.stop_playback()
            self.quality_label.setText(
                f'候选未通过质量验收，停在第{self.engine.step_index}步；详见实验记录')
        finally:
            self.future = None
            self.sidebar.setEnabled(True)

    def close(self):
        self.poll.stop()
        self.executor.shutdown(wait=False)
        super().close()


if __name__ == '__main__':
    application = QtWidgets.QApplication([])
    window = DynamicWindow()
    window.show()
    application.exec()
