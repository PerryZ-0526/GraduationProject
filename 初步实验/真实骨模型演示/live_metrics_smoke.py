"""实际运行旧在线骨面入口，验证同状态曲线和研究窗口重开。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from PyQt6 import QtWidgets
from real_bone_interactive_app import InteractiveApp


if __name__ == '__main__':
    qt = QtWidgets.QApplication([])
    app = InteractiveApp()
    app.show()
    app.toggle_metrics()
    for _ in range(3):
        app.single_step()
        qt.processEvents()
    assert app.engine.step_index == 3
    assert list(app.live_metrics.figure.axes[0].lines[0].get_xdata()) == [1, 2, 3]
    # 保存截图对应的实际记录，不能仅保留无法复核的界面图片。
    evidence = dict(time_bj=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                    scope='旧Manifold在线入口三步GUI验证，未质量验收，非新核心性能实验',
                    records=app.engine.records)
    Path(__file__).with_name('在线指标验证.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    app.save_screenshot(str(Path(__file__).with_name('在线指标验证.png')))
    app.open_research_results()
    app.research_viewer.close()
    app.open_research_results()
    assert not app.research_viewer.closed
    app.research_viewer.close()
    app.reset()
    assert len(app.live_metrics.figure.axes[0].lines[0].get_xdata()) == 0
    app.close()
    print('在线三步、同状态曲线、重置、研究窗口重开检查通过；非质量合格声明')
