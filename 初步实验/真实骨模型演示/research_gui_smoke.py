"""用真实Qt事件验证分支、拒绝状态、显示模式及截图，不生成模拟界面。"""
from pathlib import Path
from PyQt6 import QtWidgets
from research_viewer import ResearchViewer


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = ResearchViewer()
    window.show()
    app.processEvents()
    for mode in range(3):
        window.mode.setCurrentIndex(mode)
        app.processEvents()
    index = window.branches.findText('真实局部 / shift_x_1 / cuda')
    window.branches.setCurrentIndex(index)
    window.slider.setValue(window.slider.maximum())
    assert '无已保存候选' in window.status.text()
    window.files.setCurrentIndex(2)
    window.mode.setCurrentIndex(0)
    app.processEvents()
    window.slider.setValue(min(1, window.slider.maximum()))
    app.processEvents()
    window.grab().save(str(Path(__file__).with_name('真实整骨研究工作台验证.png')))
    window.close()
    assert window.closed
    print('GUI检查通过：三种显示、拒绝不冒充旧状态、切换整骨、关闭资源')
