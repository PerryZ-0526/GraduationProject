"""验证逐步维护窗口在后台完成三个已验收步骤并导出截图。"""
from pathlib import Path
from PyQt6 import QtCore, QtWidgets
from dynamic_quality_app import DynamicWindow


def main():
    app = QtWidgets.QApplication([])
    window = DynamicWindow()
    window.show()
    count = 0

    def advance():
        nonlocal count
        count += 1
        if window.engine.blocked or count > 240:
            print('GUI_SMOKE_FAILED', flush=True)
            window.close()
            return
        if window.future is None:
            if window.engine.step_index >= 3:
                window.set_view('close')
                window.toggle_display_mode()
                path = Path(__file__).parent/'逐步质量维护实验'/'逐步维护窗口.png'
                window.save_screenshot(str(path))
                print('GUI_SMOKE_PASS', window.engine.step_index, flush=True)
                window.close()
                return
            window.single_step()
        QtCore.QTimer.singleShot(250, advance)

    QtCore.QTimer.singleShot(300, advance)
    app.exec()


if __name__ == '__main__':
    main()
