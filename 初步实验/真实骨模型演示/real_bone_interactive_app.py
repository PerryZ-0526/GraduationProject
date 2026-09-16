# -*- coding: utf-8 -*-
"""真实骨面增量磨削交互式桌面原型。"""
import argparse
import csv
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import trimesh

import real_bone_demo as R
from real_bone_system_demo import build_tool, to_manifold, to_trimesh
from mesh_quality import removal_metrics


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "交互式系统输出")
PLAY_INTERVAL_MS = 90


def beijing_now():
    """返回用于实验记录的北京时间。"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class MillingEngine:
    """保存真实骨面、计划、轨迹和驻留式布尔更新状态。"""

    to_manifold = staticmethod(to_manifold)
    to_trimesh = staticmethod(to_trimesh)

    def __init__(self, mesh_path=R.SCAP_STL):
        self.load(mesh_path)

    def load(self, mesh_path):
        """加载与预置盂中心处于同一坐标系的水密三角骨面。"""
        mesh = trimesh.load(mesh_path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
            raise ValueError("输入文件没有可用的三角网格")
        if not mesh.is_watertight:
            raise ValueError("输入骨面必须是水密三角网格")
        nearby = np.linalg.norm(mesh.vertices - R.GC, axis=1) < R.FIT_R
        if int(nearby.sum()) < 20:
            raise ValueError("骨面与预置盂中心不在同一坐标系，无法可靠建立计划面")

        self.mesh_path = os.path.abspath(mesh_path)
        self.initial_mesh = mesh
        R.T_PLAN, R.N_PLAN = R.fit_glenoid_frame(mesh)
        R.R_VIEW = trimesh.geometry.align_vectors(R.N_PLAN, [0, 0, 1])
        cylinder, target, self.bounds = R.plan_solids()
        self.planned_removal = (self.to_manifold(mesh) ^ self.to_manifold(cylinder)) - self.to_manifold(target)
        self.should_remove = self.planned_removal.volume()
        self.trajectory = R.trajectory()
        self.initial_volume = mesh.volume
        self.reset()

    def reset(self):
        """恢复初始骨面并清空本次运行记录。"""
        self.bone = self.to_manifold(self.initial_mesh)
        self.current_mesh = self.initial_mesh.copy()
        self.current_tool = None
        self.current_segment = None
        self.current_radius = 0.0
        self.step_index = 0
        self.records = []
        self.delivery_mesh = None
        self.delivery_evidence = None

    def step(self):
        """执行一步真实布尔磨削，并分别记录计算管线耗时。"""
        if self.step_index >= len(self.trajectory):
            return None
        self.delivery_mesh = None
        self.delivery_evidence = None
        item = self.trajectory[self.step_index]
        pipeline_start = time.perf_counter()

        tool_start = time.perf_counter()
        phase, radius, p0, p1, tool = build_tool(item, self.bounds)
        tool_ms = (time.perf_counter() - tool_start) * 1000

        update_start = time.perf_counter()
        self.bone = self.bone - self.to_manifold(tool)
        face_count = self.bone.num_tri()
        update_ms = (time.perf_counter() - update_start) * 1000

        export_start = time.perf_counter()
        self.current_mesh = self.to_trimesh(self.bone)
        export_ms = (time.perf_counter() - export_start) * 1000

        metrics_start = time.perf_counter()
        removed = self.initial_volume - self.bone.volume()
        # 完成度只统计计划内去除，计划外误切单独计算，避免过磨抬高完成度。
        plan_metrics = removal_metrics(self.initial_volume, self.bone, self.planned_removal)
        remaining_area, overcut_area = self._risk_counts(self.current_mesh)
        metrics_ms = (time.perf_counter() - metrics_start) * 1000

        self.step_index += 1
        self.current_tool = tool
        self.current_segment = (p0, p1)
        self.current_radius = radius
        record = {
            "step": self.step_index,
            "phase": phase,
            "tool_ms": tool_ms,
            "update_ms": update_ms,
            "export_ms": export_ms,
            "metrics_ms": metrics_ms,
            "pipeline_ms": (time.perf_counter() - pipeline_start) * 1000,
            "render_ms": 0.0,
            "faces": face_count,
            "removed_mm3": removed,
            **plan_metrics,
            "remaining_area_mm2": remaining_area,
            "overcut_area_mm2": overcut_area,
        }
        self.records.append(record)
        return record

    @staticmethod
    def _risk_counts(mesh):
        """面心近似积分剩余及过磨区域面积；面积结果仍需采样收敛验证。"""
        centers = mesh.triangles_center
        normals = mesh.face_normals
        probes = centers - 0.08 * normals
        planned_probes = R.to_plan(probes)
        probe_radii = np.hypot(planned_probes[:, 0], planned_probes[:, 1])
        remaining_depth = planned_probes[:, 2] - R.D_of_r(probe_radii)
        remaining = (probe_radii < R.R_PLATE) & (remaining_depth > 0.01)

        planned_centers = R.to_plan(centers)
        center_radii = np.hypot(planned_centers[:, 0], planned_centers[:, 1])
        signed_depth = planned_centers[:, 2] - R.D_of_r(center_radii)
        overcut = ((center_radii < R.R_PLATE) & (signed_depth < -0.005)
                   & (planned_centers[:, 2]
                      > R.D_of_r(center_radii) - R.OVER_BAND))
        return float(mesh.area_faces[remaining].sum()), float(mesh.area_faces[overcut].sum())

    def display_colors(self, mesh=None):
        """生成当前骨面的剩余量、过磨和活动区域状态色。"""
        colors, _, active = R.face_colors(
            self.current_mesh if mesh is None else mesh,
            self.current_segment, self.current_radius)
        colors[active] = R.ACTIVE_COLOR
        return np.ascontiguousarray(np.clip(colors * 255, 0, 255), dtype=np.uint8)

    def export_session(self):
        """导出当前网格、逐步计时和一次运行摘要。"""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        stamp = beijing_now().strftime("%Y%m%d_%H%M%S_%f")
        prefix = os.path.join(OUTPUT_DIR, f"交互演示_{stamp}")
        mesh_path = prefix + ".ply"
        csv_path = prefix + "_计时.csv"
        summary_path = prefix + "_摘要.txt"
        self.current_mesh.export(mesh_path)

        if self.records:
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=list(self.records[0]))
                writer.writeheader()
                writer.writerows(self.records)
        else:
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as file:
                file.write("step\n")

        updates = np.asarray([row["update_ms"] for row in self.records])
        pipelines = np.asarray([row["pipeline_ms"] for row in self.records])
        last = self.records[-1] if self.records else None
        with open(summary_path, "w", encoding="utf-8") as file:
            file.write(f"生成时间（北京时间）: {beijing_now():%Y-%m-%d %H:%M:%S}\n")
            file.write(f"输入骨面: {self.mesh_path}\n")
            file.write(f"轨迹进度: {self.step_index}/{len(self.trajectory)}\n")
            file.write(f"当前面数: {len(self.current_mesh.faces)}\n")
            file.write(f"水密: {self.current_mesh.is_watertight}\n")
            if last is not None:
                file.write(f"完成度: {last['completion_pct']:.2f}%\n")
                file.write(f"累计去除: {last['removed_mm3']:.6f} mm³\n")
                file.write(f"计划内去除: {last['planned_removed_mm3']:.6f} mm³\n")
                file.write(f"计划外去除: {last['excess_removed_mm3']:.6f} mm³\n")
                file.write(
                    f"几何更新: 平均 {updates.mean():.2f} ms | "
                    f"P95 {np.percentile(updates, 95):.2f} ms | "
                    f"最大 {updates.max():.2f} ms\n")
                file.write(
                    f"完整几何管线: 平均 {pipelines.mean():.2f} ms | "
                    f"P95 {np.percentile(pipelines, 95):.2f} ms | "
                    f"最大 {pipelines.max():.2f} ms\n")
        paths = [mesh_path, csv_path, summary_path]
        if self.delivery_evidence is not None:
            evidence_path = prefix + "_质量验收.json"
            with open(evidence_path, "w", encoding="utf-8") as file:
                json.dump(self.delivery_evidence, file, ensure_ascii=False, indent=2)
            paths.append(evidence_path)
            if self.delivery_evidence['accepted']:
                delivery_path = prefix + "_优化分析网格.ply"
                self.delivery_mesh.export(delivery_path)
                paths.append(delivery_path)
        return paths


class InteractiveApp:
    """用 Qt 控件和 PyVista/VTK 呈现课题三项工作的演示界面。"""

    def __init__(self, mesh_path=R.SCAP_STL, engine_factory=MillingEngine):
        import pyvista as pv
        from PyQt6 import QtCore, QtWidgets
        from pyvistaqt import QtInteractor

        self.pv = pv
        self.QtCore = QtCore
        self.QtWidgets = QtWidgets
        self.window = QtWidgets.QMainWindow()
        self.window.setWindowTitle("旧布尔磨削演示：不保证逐步网格质量（非临床仿真）")
        self.window.resize(1480, 860)
        self.window.setMinimumSize(1120, 700)
        self.engine = engine_factory(mesh_path)
        self.view_mode = "full"
        self.display_modes = ["surface", "surface_edges", "mesh"]
        self.display_mode = "surface"
        self.mesh_actors = []
        self.tool_actor = None
        self.plan_actor = None
        self.show_delivery = False
        self.delivery_future = None

        central = QtWidgets.QWidget()
        self.window.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.plotter = QtInteractor(central)
        self.plotter.set_background("#0e141b")
        layout.addWidget(self.plotter.interactor, 1)
        self.sidebar = QtWidgets.QWidget()
        self.sidebar.setFixedWidth(350)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(375)
        scroll.setWidget(self.sidebar)
        layout.addWidget(scroll)
        self._build_sidebar()
        self._configure_style()
        # 曲线取自同一已完成状态；绘图只消费记录，不改动磨削计算或验收门槛。
        from live_metrics import LiveMetrics
        self.live_metrics = LiveMetrics(self.window)
        self.metrics_dock = QtWidgets.QDockWidget("在线记录曲线（不代表实时达标）", self.window)
        self.metrics_dock.setWidget(self.live_metrics)
        self.window.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.metrics_dock)
        self.metrics_dock.hide()

        self.timer = QtCore.QTimer()
        self.timer.setInterval(PLAY_INTERVAL_MS)
        self.timer.timeout.connect(self._tick)
        self.delivery_timer = QtCore.QTimer()
        self.delivery_timer.setInterval(100)
        self.delivery_timer.timeout.connect(self._finish_delivery)
        self._refresh_scene(reset_camera=True)

    def _configure_style(self):
        self.window.setStyleSheet("""
            QMainWindow, QWidget { background: #18212b; color: #dbe5ee;
                                  font-family: 'Microsoft YaHei UI'; font-size: 14px; }
            QPushButton { background: #293746; border: 1px solid #405267;
                          border-radius: 5px; padding: 8px; }
            QPushButton:hover { background: #35485b; }
            QProgressBar { background: #0f151c; border: 0; height: 10px; }
            QProgressBar::chunk { background: #35c7bb; }
        """)

    def _build_sidebar(self):
        layout = self.QtWidgets.QVBoxLayout(self.sidebar)
        layout.setContentsMargins(20, 20, 20, 20)
        title = self.QtWidgets.QLabel("真实骨面磨削")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        layout.addWidget(title)
        subtitle = self.QtWidgets.QLabel("肩胛盂 · 球形磨钻 · 非临床仿真")
        subtitle.setStyleSheet("color: #91a0ad;")
        layout.addWidget(subtitle)
        layout.addSpacing(16)

        buttons = self.QtWidgets.QHBoxLayout()
        self.play_button = self.QtWidgets.QPushButton("播放")
        self.play_button.clicked.connect(self.toggle_play)
        buttons.addWidget(self.play_button)
        step_button = self.QtWidgets.QPushButton("单步")
        step_button.clicked.connect(self.single_step)
        buttons.addWidget(step_button)
        reset_button = self.QtWidgets.QPushButton("重置")
        reset_button.clicked.connect(self.reset)
        buttons.addWidget(reset_button)
        layout.addLayout(buttons)

        self.progress = self.QtWidgets.QProgressBar()
        self.progress.setRange(0, len(self.engine.trajectory))
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.phase_label = self.QtWidgets.QLabel("阶段：初始")
        self.step_label = self.QtWidgets.QLabel(
            f"轨迹：0 / {len(self.engine.trajectory)}")
        layout.addWidget(self.phase_label)
        layout.addWidget(self.step_label)
        layout.addSpacing(10)

        self.metric_label = self.QtWidgets.QLabel()
        self.metric_label.setMinimumHeight(265)
        self.metric_label.setStyleSheet(
            "font-family: Consolas; font-size: 13px; color: #b9d9f4;")
        layout.addWidget(self.metric_label)
        layout.addSpacing(8)
        view_button = self.QtWidgets.QPushButton("全景 / 盂面特写")
        view_button.clicked.connect(self.toggle_view)
        layout.addWidget(view_button)
        self.display_button = self.QtWidgets.QPushButton("显示：骨面着色")
        self.display_button.clicked.connect(self.toggle_display_mode)
        layout.addWidget(self.display_button)
        self.optimize_button = self.QtWidgets.QPushButton("优化当前网格（分析交付）")
        self.optimize_button.clicked.connect(self.optimize_mesh)
        layout.addWidget(self.optimize_button)
        self.compare_button = self.QtWidgets.QPushButton("切换原始 / 优化网格")
        self.compare_button.clicked.connect(self.toggle_delivery)
        layout.addWidget(self.compare_button)
        self.quality_label = self.QtWidgets.QLabel("网格质量尚未验收；优化需数十秒")
        self.quality_label.setWordWrap(True)
        layout.addWidget(self.quality_label)
        load_button = self.QtWidgets.QPushButton("选择真实骨面 STL")
        load_button.clicked.connect(self.choose_mesh)
        layout.addWidget(load_button)
        export_button = self.QtWidgets.QPushButton("导出网格、计时与摘要")
        export_button.clicked.connect(self.export)
        layout.addWidget(export_button)
        # 研究证据与旧在线演示分开，打开前暂停计算，避免把回放误认为实时输出。
        research_button = self.QtWidgets.QPushButton("研究结果与指标曲线")
        research_button.clicked.connect(self.open_research_results)
        layout.addWidget(research_button)
        metrics_button = self.QtWidgets.QPushButton("显示 / 隐藏在线指标曲线")
        metrics_button.clicked.connect(self.toggle_metrics)
        layout.addWidget(metrics_button)
        layout.addSpacing(12)

        for text, color in [
                ("■ 蓝色：剩余待去除", "#61a7ff"),
                ("■ 橙色：当前磨削区", "#ff7a2f"),
                ("■ 红黄：过磨警示", "#ff6b5f"),
                ("━ 青色：计划边界", "#39d0c8")]:
            label = self.QtWidgets.QLabel(text)
            label.setStyleSheet(f"color: {color};")
            layout.addWidget(label)
        layout.addStretch(1)
        note = self.QtWidgets.QLabel(
            "鼠标左键旋转 · 滚轮缩放 · 中键平移\n"
            "当前加载器使用预置盂中心，其他坐标系模型会被拒绝。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #91a0ad;")
        layout.addWidget(note)
        self._update_metrics(None)

    def _polydata(self, mesh):
        faces = np.column_stack((np.full(len(mesh.faces), 3), mesh.faces)).ravel()
        return self.pv.PolyData(np.asarray(mesh.vertices), faces)

    def _refresh_scene(self, reset_camera=False):
        render_start = time.perf_counter()
        # 在线更新和显示模式切换保留用户相机；仅显式加载、重置或视角按钮重新取景。
        saved_camera = self.pv.Camera()
        saved_camera.DeepCopy(self.plotter.camera)
        for actor in self.mesh_actors:
            self.plotter.remove_actor(actor)
        self.mesh_actors = []
        if self.tool_actor is not None:
            self.plotter.remove_actor(self.tool_actor)
            self.tool_actor = None
        display_mesh = (self.engine.delivery_mesh if self.show_delivery and
                        self.engine.delivery_mesh is not None else self.engine.current_mesh)
        poly = self._polydata(display_mesh)
        poly.cell_data["状态色"] = self.engine.display_colors(display_mesh)
        if self.display_mode == "surface":
            self.mesh_actors.append(self.plotter.add_mesh(
                poly, scalars="状态色", rgb=True, smooth_shading=False,
                show_scalar_bar=False, reset_camera=False))
        elif self.display_mode == "surface_edges":
            self.mesh_actors.append(self.plotter.add_mesh(
                poly, scalars="状态色", rgb=True, smooth_shading=False,
                show_edges=True, edge_color="#253342", line_width=1,
                show_scalar_bar=False, reset_camera=False))
        else:
            # 点线模式不绘制填充面，同时显示三角边与顶点。
            self.mesh_actors.append(self.plotter.add_mesh(
                poly, style="wireframe", color="#75baff", line_width=1,
                lighting=False, reset_camera=False))
            self.mesh_actors.append(self.plotter.add_mesh(
                poly, style="points", color="#ffe08a", point_size=4,
                render_points_as_spheres=True, lighting=False, reset_camera=False))
        if self.engine.current_tool is not None:
            tool_style = "wireframe" if self.display_mode == "mesh" else "surface"
            self.tool_actor = self.plotter.add_mesh(
                self._polydata(self.engine.current_tool), style=tool_style,
                color="#ff5914", opacity=0.75 if tool_style == "wireframe" else 0.30, reset_camera=False)
        if self.plan_actor is None:
            angles = np.linspace(0, 2 * np.pi, 129)
            ring = np.asarray([R.to_world([R.R_PLATE * np.cos(angle),
                                          R.R_PLATE * np.sin(angle), 0.0])
                               for angle in angles])
            self.plan_actor = self.plotter.add_lines(
                ring, connected=True, color="#39d0c8", width=3)
        if reset_camera:
            self.set_view(self.view_mode)
        else:
            self.plotter.camera.DeepCopy(saved_camera)
            self.plotter.reset_camera_clipping_range()
        self.plotter.render()
        self.last_render_ms = (time.perf_counter() - render_start) * 1000

    def set_view(self, mode):
        if mode == "close":
            normal = np.asarray(R.N_PLAN, dtype=float)
            up = np.cross(normal, [1.0, 0.0, 0.0])
            if np.linalg.norm(up) < 0.2:
                up = np.cross(normal, [0.0, 1.0, 0.0])
            up /= np.linalg.norm(up)
            self.plotter.camera_position = [R.GC + normal * 60.0, R.GC, up]
            self.plotter.enable_parallel_projection()
            self.plotter.camera.parallel_scale = 24.0
        else:
            self.plotter.disable_parallel_projection()
            self.plotter.reset_camera()
            self.plotter.camera.azimuth = -30
            self.plotter.camera.elevation = 25
        self.plotter.reset_camera_clipping_range()

    def toggle_view(self):
        self.view_mode = "close" if self.view_mode == "full" else "full"
        self.set_view(self.view_mode)
        self.plotter.render()

    def toggle_display_mode(self):
        """循环切换骨面、带边骨面和仅点线三角网格。"""
        index = (self.display_modes.index(self.display_mode) + 1) % len(
            self.display_modes)
        self.display_mode = self.display_modes[index]
        labels = {
            "surface": "显示：骨面着色",
            "surface_edges": "显示：骨面 + 三角边",
            "mesh": "显示：仅点线网格",
        }
        self.display_button.setText(labels[self.display_mode])
        self._refresh_scene()

    def single_step(self):
        self.show_delivery = False
        record = self.engine.step()
        if record is None:
            self.stop_playback()
            return
        self._refresh_scene()
        record['render_ms'] = self.last_render_ms
        self.quality_label.setText("原始布尔网格；当前步骤尚未质量验收")
        self._update_metrics(record)

    def optimize_mesh(self):
        """后台优化暂停时的快照；验收通过后才能作为分析副本显示或导出。"""
        from concurrent.futures import ThreadPoolExecutor
        from mesh_quality import validated_delivery

        self.stop_playback()
        self.quality_label.setText("局部重网格与误差验收中……")
        self.sidebar.setEnabled(False)
        self.delivery_executor = ThreadPoolExecutor(max_workers=1)
        self.delivery_future = self.delivery_executor.submit(
            validated_delivery, self.engine.current_mesh.copy(), R.GC.copy())
        self.delivery_timer.start()

    def _finish_delivery(self):
        if self.delivery_future is None or not self.delivery_future.done():
            return
        self.delivery_timer.stop()
        try:
            mesh, evidence = self.delivery_future.result()
            self.engine.delivery_evidence = evidence
            if evidence['accepted']:
                self.engine.delivery_mesh = mesh
                self.show_delivery = True
                self.quality_label.setText(
                    f"优化副本：{len(mesh.faces):,} 面；劣质面 "
                    f"{evidence['after']['bad_q_pct']:.2f}%\n"
                    f"采样验收通过；总耗时 {evidence['total_ms']/1000:.1f} 秒")
                self._refresh_scene()
            else:
                self.engine.delivery_mesh = None
                self.show_delivery = False
                self.quality_label.setText("质量验收未通过；保留原始网格，导出可查看原因")
        except Exception as exc:
            self.quality_label.setText(f"优化失败，保留原始网格：{exc}")
        finally:
            self.sidebar.setEnabled(True)
            self.delivery_executor.shutdown(wait=False)
            self.delivery_future = None

    def toggle_delivery(self):
        if self.engine.delivery_mesh is not None:
            self.show_delivery = not self.show_delivery
            self._refresh_scene()

    def toggle_play(self):
        if self.timer.isActive():
            self.stop_playback()
        else:
            self.play_button.setText("暂停")
            self.timer.start()
            self._tick()

    def _tick(self):
        self.single_step()
        if self.engine.step_index >= len(self.engine.trajectory):
            self.stop_playback()

    def stop_playback(self):
        self.timer.stop()
        self.play_button.setText("播放")

    def reset(self):
        self.stop_playback()
        self.engine.reset()
        self.show_delivery = False
        self.quality_label.setText("已重置；当前步骤尚未质量验收")
        self.progress.setValue(0)
        self.phase_label.setText("阶段：初始")
        self._update_metrics(None)
        self._refresh_scene(reset_camera=True)

    def choose_mesh(self):
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.window, "选择真实骨面 STL", "", "STL 三角网格 (*.stl)")
        if not path:
            return
        self.stop_playback()
        try:
            self.engine.load(path)
        except Exception as exc:
            self.QtWidgets.QMessageBox.critical(self.window, "加载失败", str(exc))
            return
        if self.plan_actor is not None:
            self.plotter.remove_actor(self.plan_actor)
            self.plan_actor = None
        self.progress.setRange(0, len(self.engine.trajectory))
        self._refresh_scene(reset_camera=True)
        self._update_metrics(None)

    def export(self):
        try:
            paths = self.engine.export_session()
        except Exception as exc:
            self.QtWidgets.QMessageBox.critical(self.window, "导出失败", str(exc))
            return
        self.QtWidgets.QMessageBox.information(
            self.window, "导出完成", "已保存：\n" + "\n".join(paths))

    def _update_metrics(self, record):
        # 控件初始化时绘图区可能尚未创建；之后与当前已完成记录同步刷新。
        if hasattr(self, 'live_metrics') and self.metrics_dock.isVisible():
            self.live_metrics.refresh(self.engine.records)
        self.progress.setValue(self.engine.step_index)
        self.step_label.setText(
            f"轨迹：{self.engine.step_index} / {len(self.engine.trajectory)}")
        if record is None:
            self.metric_label.setText(
                f"当前面数       {len(self.engine.current_mesh.faces):,}\n"
                "完成度           0.0 %\n累计去除         0.0 mm³\n\n"
                "几何更新         -- ms\n网格导出         -- ms\n"
                "几何管线         -- ms\n界面渲染         -- ms")
            return
        self.phase_label.setText(f"阶段：{record['phase']}")
        self.metric_label.setText(
            f"计算面数       {record['faces']:,}\n"
            f"完成度         {record['completion_pct']:7.2f} %\n"
            f"累计去除       {record['removed_mm3']:7.2f} mm³\n"
            f"剩余面积≈      {record['remaining_area_mm2']:.2f} mm²\n"
            f"近计划过磨≈    {record['overcut_area_mm2']:.2f} mm²\n"
            f"计划外去除     {record['excess_removed_mm3']:.3f} mm³\n"
            f"几何更新       {record['update_ms']:7.2f} ms\n"
            f"网格导出       {record['export_ms']:7.2f} ms\n"
            f"几何管线       {record['pipeline_ms']:7.2f} ms\n"
            f"界面渲染       {record['render_ms']:7.2f} ms")

    def open_research_results(self):
        """使用现有Qt/PyVista组件查看逐状态网格及质量、误差、耗时证据。"""
        from research_viewer import ResearchViewer
        self.stop_playback()
        if not hasattr(self, 'research_viewer') or self.research_viewer.closed:
            self.research_viewer = ResearchViewer(self.window)
        self.research_viewer.show()
        self.research_viewer.raise_()

    def toggle_metrics(self):
        """展开当前在线计算记录；未知质量保持未测量而不是填零。"""
        self.live_metrics.refresh(self.engine.records)
        self.metrics_dock.setVisible(not self.metrics_dock.isVisible())

    def save_screenshot(self, path):
        self.window.grab().save(path)

    def show(self):
        self.window.show()

    def close(self):
        self.stop_playback()
        self.plotter.close()
        self.window.close()


def self_test(step_count):
    """无窗口验证真实数据加载、状态推进、计时记录和水密性。"""
    engine = MillingEngine()
    for _ in range(step_count):
        if engine.step() is None:
            break
    if engine.step_index != min(step_count, len(engine.trajectory)):
        raise RuntimeError("自检推进步数不一致")
    if not engine.current_mesh.is_watertight:
        raise RuntimeError("自检后的骨面不水密")
    last = engine.records[-1] if engine.records else None
    print(f"SELF_TEST_OK steps={engine.step_index} faces={len(engine.current_mesh.faces)} "
          f"watertight={engine.current_mesh.is_watertight} "
          f"update_ms={last['update_ms'] if last else 0.0:.2f}")


def run_gui(mesh_path, screenshot_path=None, screenshot_steps=8, optimize=False):
    """启动桌面窗口；可选自动推进并保存验证截图。"""
    from PyQt6 import QtCore, QtWidgets

    qt_app = QtWidgets.QApplication([])
    app = InteractiveApp(mesh_path)
    app.show()
    if screenshot_path:
        def save_result():
            if app.delivery_future is not None:
                QtCore.QTimer.singleShot(100, save_result)
                return
            app.save_screenshot(os.path.abspath(screenshot_path))
            if optimize:
                paths = app.engine.export_session()
                print('GUI_DELIVERY', app.engine.delivery_evidence['accepted'], paths, flush=True)
            QtCore.QTimer.singleShot(100, app.close)

        def capture_and_close():
            for _ in range(screenshot_steps):
                app.single_step()
            app.set_view("close")
            # 优化验证使用带边骨面，其余截图仍使用点线模式检查拓扑。
            app.toggle_display_mode()
            if optimize:
                app.optimize_mesh()
            else:
                app.toggle_display_mode()
            QtCore.QTimer.singleShot(100, save_result)
        QtCore.QTimer.singleShot(500, capture_and_close)
    qt_app.exec()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-bool', action='store_true', help='显式打开旧布尔演示；不保证逐步网格质量')
    parser.add_argument("--mesh", default=R.SCAP_STL, help="真实骨面 STL 路径")
    parser.add_argument("--self-test", action="store_true", help="执行无窗口自检")
    parser.add_argument("--steps", type=int, default=3, help="自检推进步数")
    parser.add_argument("--screenshot", help="自动保存 VTK 验证截图并退出")
    parser.add_argument("--optimize", action="store_true", help="截图前执行质量优化并导出")
    args = parser.parse_args()
    # 默认入口转入实验门控在线模式；旧布尔演示必须显式选择，不能再冒充逐步质量保证。
    if not args.legacy_bool and not args.self_test:
        if args.mesh != R.SCAP_STL or args.screenshot or args.optimize:
            parser.error('受限在线模式仅支持既有真实骨面；旧演示参数须显式加--legacy-bool')
        from validated_online import run
        run()
        return
    if args.self_test:
        self_test(max(args.steps, 0))
    else:
        run_gui(args.mesh, args.screenshot, max(args.steps, 0), args.optimize)


if __name__ == "__main__":
    main()
