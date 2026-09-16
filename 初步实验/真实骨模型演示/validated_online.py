"""受限真实骨面在线重建：复用实验门控，界面只消费验收完成的独立快照。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import importlib.util
import hashlib
import json
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
MODEL_DIR = HERE.parent / '局部适用域与核显计算'
sys.path.insert(0, str(MODEL_DIR))
from local_model import LocalPatch
from dynamic import iter_sequence
from real_patch import local_trajectory


class ValidatedSession:
    """只支持既有真实标本和16段水平交叉轨迹，不接收任意骨面或原138段计划。"""
    def __init__(self, trajectory=None):
        # 使用独立模块名加载既有初态，避免多个experiment.py在导入缓存中串用。
        spec = importlib.util.spec_from_file_location('validated_candidate_loader', MODEL_DIR / 'experiment.py')
        loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader)
        self.candidate, chart = loader.load_candidate()
        self.trajectory = list(local_trajectory(1.8) if trajectory is None else trajectory)
        self.iterator = iter_sequence(self.candidate, chart, model_factory=LocalPatch, trajectory=self.trajectory)
        self.records, self.snapshots = [], []
        self.finished = False
        self.step = 0

    def advance(self):
        if self.finished:
            return None
        started = time.perf_counter()
        try:
            model, row = next(self.iterator)
        except StopIteration:
            self.finished = True
            return None
        row = dict(row) if row is not None else dict(step=0, accepted=True,
            min_angle_deg=float(model.angles.min()), min_q=float(model.q.min()),
            error_bound_mm=float(model.bounds.max()), initial=True)
        row['wall_ms'] = (time.perf_counter() - started) * 1000
        row['time_beijing'] = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
        self.records.append(row)
        if not row['accepted']:
            self.finished = True
            return None, row
        whole = self.candidate['whole'].copy()
        whole.vertices[self.candidate['mapping']] = model.vertices
        self.step = row['step']
        # 快照完全脱离后台模型；GUI不读取计算中间态。
        self.snapshots.append(np.asarray(whole.vertices).copy())
        if self.step == len(self.trajectory):
            self.finished = True
        return whole, row


def create_window():
    from PyQt6 import QtCore, QtWidgets
    import pyvista as pv
    from pyvistaqt import QtInteractor
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

    class Window(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('真实骨面 · 逐步验收在线重建（受限CPU参照）')
            self.resize(1380, 920)
            self.executor = ThreadPoolExecutor(max_workers=1)
            self.future = self.session = self.mesh = None
            self.playing = self.closing = False
            self.published_step = 0
            self.rows = []
            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            layout = QtWidgets.QVBoxLayout(central)
            scope = QtWidgets.QLabel('在线重新计算 / CPU参照 / 非实时达标 / 非临床使用\n'
                '真实骨面：固定局部图域、半径3 mm、球心z=1.8 mm、16段水平交叉轨迹；不支持原138段裁剪、跨域或竖直磨削。\n'
                '重建域含过渡带：角≥25°、q≥0.4、误差证书≤0.1 mm；外部原骨面保留既有质量，不保证全骨每面均达标。')
            scope.setWordWrap(True)
            layout.addWidget(scope)
            self.plotter = QtInteractor(central)
            self.plotter.set_background('#102029')
            layout.addWidget(self.plotter.interactor, 3)
            self.figure = Figure(figsize=(11, 2.2), layout='constrained')
            self.canvas = FigureCanvasQTAgg(self.figure)
            layout.addWidget(self.canvas, 1)
            self.status = QtWidgets.QLabel('初态正在重新验收，尚无已发布网格')
            self.status.setWordWrap(True)
            layout.addWidget(self.status)
            controls = QtWidgets.QHBoxLayout()
            layout.addLayout(controls)
            self.step_button = QtWidgets.QPushButton('单步计算')
            self.step_button.clicked.connect(self.single_step)
            self.play_button = QtWidgets.QPushButton('播放计算')
            self.play_button.clicked.connect(self.toggle_play)
            self.mode = QtWidgets.QComboBox()
            self.mode.addItems(['骨面＋三角边', '仅点线三角网格'])
            self.mode.currentIndexChanged.connect(self.render_mesh)
            self.show_tool = QtWidgets.QCheckBox('显示已验收刀位')
            self.show_tool.setChecked(True)
            self.show_tool.toggled.connect(self.render_mesh)
            reset = QtWidgets.QPushButton('重置视角')
            reset.clicked.connect(self.reset_view)
            self.restart_button = QtWidgets.QPushButton('重新开始')
            self.restart_button.clicked.connect(self.restart)
            export = QtWidgets.QPushButton('导出本次证据')
            export.clicked.connect(self.export)
            research = QtWidgets.QPushButton('研究结果回放')
            research.clicked.connect(self.open_research)
            for widget in (self.step_button, self.play_button, self.mode, self.show_tool, reset, self.restart_button, export, research):
                controls.addWidget(widget)
            self.poll = QtCore.QTimer(self)
            self.poll.setInterval(30)
            self.poll.timeout.connect(self.finish_step)
            self.poll.start()
            self.single_step()

        def compute(self):
            if self.session is None:
                self.session = ValidatedSession()
            return self.session.advance()

        def single_step(self):
            if self.future is not None or (self.session is not None and self.session.finished):
                return
            self.step_button.setEnabled(False)
            self.restart_button.setEnabled(False)
            self.status.setText('正在计算和验收；显示仍为最后合格状态，工具和网格不会提前推进')
            self.future = self.executor.submit(self.compute)

        def toggle_play(self):
            self.playing = not self.playing
            self.play_button.setText('暂停（当前步完成后生效）' if self.playing else '播放计算')
            if self.playing:
                self.single_step()

        def finish_step(self):
            if self.future is None or not self.future.done():
                return
            try:
                result = self.future.result()
                if result is not None:
                    mesh, row = result
                    self.rows.append(row)
                    if mesh is not None:
                        first = self.mesh is None
                        self.mesh = mesh
                        self.published_step = row['step']
                        started = time.perf_counter()
                        self.render_mesh()
                        if first:
                            self.reset_view()
                        row['render_ms'] = (time.perf_counter() - started) * 1000
                        self.status.setText(f"已发布 {row['step']}/16；角 {row['min_angle_deg']:.3f}°；"
                            f"q {row['min_q']:.3f}；误差证书 {row['error_bound_mm']:.5f} mm；"
                            f"计算验收 {row['wall_ms']:.0f} ms（100 ms仅为目标）")
                    else:
                        self.status.setText(f"第{row['step']}步拒绝：{row.get('reason', '未通过验收')}；"
                                            f'保留第{self.session.step}步合格网格，已停止')
                    self.draw_metrics()
            except Exception as exc:
                self.playing = False
                if self.session is not None:
                    self.session.finished = True
                self.status.setText(f'计算错误，停止发布并保留最后合格状态：{exc}')
            finally:
                self.future = None
                finished = self.session is None or self.session.finished
                self.step_button.setEnabled(not finished)
                self.restart_button.setEnabled(True)
                if finished:
                    self.playing = False
                    self.play_button.setEnabled(False)
                self.play_button.setText('暂停（当前步完成后生效）' if self.playing else '播放计算')
                if self.closing:
                    self.close()
                elif self.playing:
                    self.single_step()

        def restart(self):
            if self.future is not None:
                return
            self.playing = False
            self.session = self.mesh = None
            self.published_step = 0
            self.rows = []
            self.play_button.setEnabled(True)
            self.play_button.setText('播放计算')
            self.plotter.clear()
            self.draw_metrics()
            self.single_step()

        def render_mesh(self):
            if self.mesh is None:
                return
            camera = pv.Camera()
            camera.DeepCopy(self.plotter.camera)
            self.plotter.clear()
            mesh = self.mesh
            poly = pv.PolyData(mesh.vertices, np.column_stack([np.full(len(mesh.faces), 3), mesh.faces]).ravel())
            # 共边拼接的末段面是重建域；颜色只标区域，不冒充全骨质量标签。
            poly.cell_data['region'] = np.r_[np.zeros(len(mesh.faces)-len(self.session.candidate['faces'])),
                                             np.ones(len(self.session.candidate['faces']))]
            self.plotter.add_mesh(poly, scalars='region', cmap=['#cdbb91', '#69b6b4'], show_scalar_bar=False,
                style='wireframe' if self.mode.currentIndex() else 'surface', show_edges=True, reset_camera=False)
            if self.mode.currentIndex():
                self.plotter.add_mesh(poly, style='points', point_size=2, color='#69b6b4', reset_camera=False)
            # 刀位只取GUI已发布步号；后台完成但尚未刷新网格时，也不能让刀位提前移动。
            if self.show_tool.isChecked() and self.published_step:
                tool = self.session.trajectory[self.published_step-1]
                sphere = pv.Sphere(radius=tool.radius, center=(*tool.end, tool.z), theta_resolution=20, phi_resolution=16)
                self.plotter.add_mesh(sphere, color='#ef913a', style='wireframe', opacity=.35, reset_camera=False)
            self.plotter.camera.DeepCopy(camera)
            self.plotter.reset_camera_clipping_range()
            self.plotter.render()

        def reset_view(self):
            self.plotter.camera_position = [(4, -30, 37), (-1, 0, -2), (0, 1, 0)]
            self.plotter.camera.parallel_projection = True
            self.plotter.camera.parallel_scale = 14
            self.plotter.reset_camera_clipping_range()
            self.plotter.render()

        def open_research(self):
            from research_viewer import ResearchViewer
            if not hasattr(self, 'research_viewer') or self.research_viewer.closed:
                self.research_viewer = ResearchViewer(self)
            self.research_viewer.show()
            self.research_viewer.raise_()

        def draw_metrics(self):
            self.figure.clear()
            for axis, key, title, limit in zip(self.figure.subplots(1, 3),
                    ['min_angle_deg', 'error_bound_mm', 'wall_ms'],
                    ['Minimum angle (deg)', 'Error bound (mm)', 'Compute + audit (ms)'], [25, .1, 100]):
                axis.plot([r['step'] for r in self.rows], [r.get(key, np.nan) for r in self.rows], '.-')
                axis.axhline(limit, color='red', linestyle='--')
                axis.set_title(title)
                axis.set_xlabel('Attempted step')
            self.canvas.draw_idle()

        def export(self):
            if self.future is not None or self.mesh is None:
                self.status.setText('请等待当前计算结束后导出')
                return
            folder = HERE / '在线逐步验收输出' / datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S_%f')
            folder.mkdir(parents=True)
            np.savez_compressed(folder / 'states.npz', snapshots=self.session.snapshots, faces=self.mesh.faces)
            (folder / 'records.json').write_text(json.dumps(self.rows, ensure_ascii=False, indent=2), encoding='utf-8')
            source = HERE.parent / '边界过渡带联合重建/实验结果/joint.npz'
            metadata = dict(time_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S'),
                backend='CPU float64', source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                trajectory=[tool.__dict__ for tool in self.session.trajectory],
                thresholds=dict(angle_deg=25, q=.4, error_mm=.1),
                scope='固定局部重建域含过渡带；整骨拓扑与自交复核；不保证外部原网格形状质量',
                snapshots='初态及接受步；拒绝步只有记录，没有新快照',
                timing='wall_ms含生成器更新和验收；不含初态文件加载、显示传输与图表绘制；render_ms单独记录')
            (folder / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
            self.figure.savefig(folder / '指标.png', dpi=150)
            self.status.setText(f'已导出逐状态记录及双精度整骨快照：{folder}')

        def closeEvent(self, event):
            self.playing = False
            if self.future is not None:
                self.closing = True
                self.status.setText('等待当前验收结束后关闭，不强杀计算线程')
                event.ignore()
                return
            self.poll.stop()
            self.executor.shutdown(wait=False)
            self.plotter.close()
            event.accept()

    return Window()


def run():
    from PyQt6 import QtWidgets
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = create_window()
    window.show()
    application.exec()


if __name__ == '__main__':
    run()
