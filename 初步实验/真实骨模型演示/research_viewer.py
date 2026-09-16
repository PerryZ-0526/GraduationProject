"""研究结果工作台：网格与逐状态指标联动；回放绝不标为在线实时计算。"""
import argparse
from pathlib import Path
import numpy as np
import pyvista as pv
from PyQt6 import QtCore, QtWidgets
from pyvistaqt import QtInteractor
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from research_results import discover, series_from_file


class ResearchViewer(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('骨面研究工作台 · 证据回放 / 非在线计算')
        self.resize(1440, 900)
        self.setMinimumSize(980, 680)
        self.setStyleSheet("QWidget {font-family:'Microsoft YaHei UI';font-size:13px;} QPushButton,QComboBox {padding:6px;} QLabel {padding:4px;}")
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        header = QtWidgets.QLabel('研究证据工作台  |  结果回放，不代表实时计算或临床可用')
        header.setStyleSheet('background:#192b36;color:#ffffff;font-size:17px;padding:12px;')
        layout.addWidget(header)
        controls = QtWidgets.QHBoxLayout()
        self.files = QtWidgets.QComboBox()
        for path in discover():
            self.files.addItem(f'{path.parents[1].name} / {path.parent.name}', str(path))
        controls.addWidget(self.files, 2)
        load = QtWidgets.QPushButton('打开结果 JSON')
        load.clicked.connect(self.open_file)
        controls.addWidget(load)
        self.branches = QtWidgets.QComboBox()
        controls.addWidget(self.branches, 2)
        layout.addLayout(controls)
        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.plotter = QtInteractor(split)
        self.plotter.set_background('#102029')
        split.addWidget(self.plotter.interactor)
        self.figure = Figure(figsize=(12, 3), layout='constrained')
        self.canvas = FigureCanvasQTAgg(self.figure)
        split.addWidget(self.canvas)
        split.setSizes([500, 280])
        layout.addWidget(split, 1)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        bottom = QtWidgets.QHBoxLayout()
        self.play = QtWidgets.QPushButton('播放回放')
        self.play.clicked.connect(self.toggle_play)
        bottom.addWidget(self.play)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        bottom.addWidget(self.slider, 1)
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(['骨面＋三角边', '仅点线三角网格', '形状差面标红'])
        bottom.addWidget(self.mode)
        reset = QtWidgets.QPushButton('重置视角')
        reset.clicked.connect(self.plotter.reset_camera)
        bottom.addWidget(reset)
        export = QtWidgets.QPushButton('导出指标图')
        export.clicked.connect(self.export_plot)
        bottom.addWidget(export)
        layout.addLayout(bottom)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.advance)
        self.rows = []
        self.closed = False
        self.files.currentIndexChanged.connect(self.load_selected)
        self.branches.currentIndexChanged.connect(self.change_series)
        self.slider.valueChanged.connect(self.show_step)
        self.mode.currentIndexChanged.connect(self.show_step)
        self.canvas.mpl_connect('button_press_event', self.select_plot)
        if self.files.count():
            self.load_selected()

    def open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, '选择实验结果', '', 'JSON (*.json)')
        if path:
            self.files.addItem(Path(path).parent.name, path)
            self.files.setCurrentIndex(self.files.count()-1)

    def load_selected(self):
        self.timer.stop()
        self.play.setText('播放回放')
        try:
            self.series = series_from_file(self.files.currentData())
            self.branches.blockSignals(True)
            self.branches.clear()
            self.branches.addItems([name for name, _ in self.series])
            self.branches.blockSignals(False)
            self.change_series()
        except (ValueError, OSError, KeyError) as exc:
            self.branches.blockSignals(False)
            self.rows = []
            self.plotter.clear()
            self.figure.clear()
            self.canvas.draw_idle()
            self.status.setText(f'无法读取证据：{exc}')

    def change_series(self):
        if self.branches.currentIndex() < 0:
            return
        self.timer.stop()
        self.play.setText('播放回放')
        self.rows = self.series[self.branches.currentIndex()][1]
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(self.rows)-1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.show_step()
        self.plotter.reset_camera()

    def show_step(self, *_):
        if not self.rows:
            return
        row = self.rows[self.slider.value()]
        # 逐状态替换actor时保存完整相机，避免首次actor或空候选恢复触发隐式重新取景。
        saved_camera = pv.Camera()
        saved_camera.DeepCopy(self.plotter.camera)
        self.plotter.clear()
        path = row.get('mesh')
        available = path and Path(path).exists() and (Path(path).suffix != '.npz' or row.get('snapshot') is not None)
        message = ''
        if available:
            try:
                if Path(path).suffix == '.npz':
                    with np.load(path) as saved:
                        faces = np.column_stack([np.full(len(saved['faces']), 3), saved['faces']])
                        mesh = pv.PolyData(saved['snapshots'][row['snapshot']], faces)
                else:
                    mesh = pv.read(path).triangulate()
                mode = self.mode.currentIndex()
                if mode == 1:
                    self.plotter.add_mesh(mesh, style='wireframe', color='#d7d3b7', line_width=1, reset_camera=False)
                    self.plotter.add_mesh(mesh, style='points', color='#68c9c0', point_size=3, reset_camera=False)
                elif mode == 2:
                    # 颜色覆盖当前显示的全部三角形；与仅统计变更面的报告口径明确区分。
                    angles = mesh.cell_quality(quality_measure='min_angle')['min_angle']
                    mesh['bad'] = (~np.isfinite(angles) | (angles < 25)).astype(float)
                    self.plotter.add_mesh(mesh, scalars='bad', cmap=['#c7b891', '#e75436'], clim=[0, 1], show_edges=True, show_scalar_bar=False, reset_camera=False)
                    message = '；红色为显示面最小角<25°（仅形状提示，非完整验收）'
                else:
                    self.plotter.add_mesh(mesh, color='#c7b891', show_edges=True, edge_color='#304552', reset_camera=False)
            except (ValueError, OSError, IndexError) as exc:
                message = f'；网格读取失败：{exc}'
        else:
            message = '；该步骤无已保存候选，不以旧网格代替'
        self.status.setText(f"步骤 {row['step']} | {row.get('status', '未验收')} | 证据回放{message}")
        self.plotter.camera.DeepCopy(saved_camera)
        self.plotter.reset_camera_clipping_range()
        self.plotter.render()
        self.draw_metrics(row['step'])

    def draw_metrics(self, selected):
        self.figure.clear()
        axes = self.figure.subplots(1, 3)
        fields = [('min_angle_deg', 'Minimum angle (deg)', 25), ('error_bound_mm', 'Error certificate (mm)', .1), ('total_ms', 'Recorded compute time (ms)', 100)]
        steps = [r['step'] for r in self.rows]
        for ax, (field, label, threshold) in zip(axes, fields):
            values = [r.get(field, r.get('elapsed_ms')) if field == 'total_ms' else r.get(field) for r in self.rows]
            values = [np.nan if v is None else v for v in values]
            ax.plot(steps, values, '.-', color='#187c82')
            ax.axhline(threshold, ls='--', color='#c65a32', lw=1)
            ax.axvline(selected, color='#334552', lw=1)
            ax.set_title(label, fontsize=10)
            ax.set_xlabel('Step')
            ax.grid(alpha=.15)
            if not np.isfinite(values).any():
                ax.text(.5, .5, 'Not measured', transform=ax.transAxes, ha='center')
        self.canvas.draw_idle()

    def select_plot(self, event):
        if event.xdata is not None and self.rows:
            self.slider.setValue(int(np.argmin([abs(r['step']-event.xdata) for r in self.rows])))

    def toggle_play(self):
        if self.timer.isActive():
            self.timer.stop()
        else:
            self.timer.start()
        self.play.setText('暂停回放' if self.timer.isActive() else '播放回放')

    def advance(self):
        if self.slider.value() == self.slider.maximum():
            self.timer.stop()
            self.play.setText('播放回放')
        else:
            self.slider.setValue(self.slider.value()+1)

    def export_plot(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, '导出指标图', '指标.png', 'PNG (*.png)')
        if path:
            self.figure.savefig(path, dpi=180)

    def closeEvent(self, event):
        self.closed = True
        self.timer.stop()
        self.plotter.close()
        super().closeEvent(event)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot')
    args = parser.parse_args()
    app = QtWidgets.QApplication([])
    window = ResearchViewer()
    window.show()
    if args.screenshot:
        def capture():
            window.grab().save(args.screenshot)
            window.close()
        QtCore.QTimer.singleShot(1500, capture)
    app.exec()
