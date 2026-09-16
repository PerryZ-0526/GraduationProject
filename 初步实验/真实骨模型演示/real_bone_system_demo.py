# -*- coding: utf-8 -*-
"""
真实骨面驻留式更新系统演示
============================
在真实 CT 肩胛骨上运行 138 步五相位磨削，骨网格始终驻留 manifold3d 内核。
完整记录工具构造、几何更新、网格导出和指标计算耗时；抽取代表步骤生成
整骨视图、盂面特写和数据面板组成的答辩演示 GIF。
"""
import csv
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh, Mesh64
from PIL import Image, ImageDraw, ImageFont

import real_bone_demo as R

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "驻留式系统演示")
FRAMES = os.path.join(OUT, "frames")
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
GIF_MS = 260
DISPLAY_INTERVAL = 10

# Windows 终端默认 GBK 无法输出“mm³”，统一改为 UTF-8。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def to_manifold(mesh, precision64=False):
    """把 Trimesh 转为内核网格；动态维护可显式保留双精度。"""
    return Manifold(mesh=(Mesh64 if precision64 else Mesh)(
        vert_properties=np.array(mesh.vertices, dtype=np.float64 if precision64 else np.float32, order='C', copy=True),
        tri_verts=np.array(mesh.faces, dtype=np.uint64 if precision64 else np.uint32, order='C', copy=True),
    ))


def to_trimesh(manifold, precision64=False):
    """保留索引导出；双精度避免切口的近邻顶点量化重合。"""
    mesh = manifold.to_mesh64() if precision64 else manifold.to_mesh()
    return trimesh.Trimesh(
        vertices=mesh.vert_properties,
        faces=mesh.tri_verts,
        process=False,
    )


def build_tool(item, bounds):
    """构造受计划边界约束的真实位姿工具扫掠体。"""
    phase, radius, p0_plan, p1_plan = item
    p0, p1 = R.to_world(p0_plan), R.to_world(p1_plan)
    tool = trimesh.boolean.intersection(
        [R.sweep_capsule(radius, p0, p1), bounds[phase]],
        engine="manifold",
    )
    return phase, radius, p0, p1, tool


def selected_steps(trajectory):
    """选择均匀步骤和相位边界，兼顾动画连贯性与生成耗时。"""
    selected = {0, len(trajectory)}
    selected.update(range(DISPLAY_INTERVAL, len(trajectory), DISPLAY_INTERVAL))
    previous = trajectory[0][0]
    for step, item in enumerate(trajectory, 1):
        if item[0] != previous:
            selected.update({step - 1, step})
            previous = item[0]
    return selected


def font(size):
    """加载 Windows 中文字体。"""
    return ImageFont.truetype(FONT_PATH, size=size)


def fit_image(image, size):
    """等比缩放图像并居中放入指定尺寸。"""
    image = image.copy()
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "#171d24")
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.paste(image, (x, y))
    return canvas


def draw_metric_panel(draw, row, x0, width, height):
    """绘制适合论文截图和答辩展示的实时指标面板。"""
    white = "#f4f7fa"
    muted = "#9caab7"
    cyan = "#3bd2c7"
    orange = "#ff7a2f"
    blue = "#4d9cff"
    red = "#ff625f"
    draw.rounded_rectangle((x0, 28, x0 + width, height - 28), radius=18,
                           fill="#222b35", outline="#3b4652", width=2)
    draw.text((x0 + 28, 52), "实时状态", font=font(30), fill=white)
    draw.text((x0 + 28, 100), f"阶段  {row['phase']}",
              font=font(23), fill=orange)
    draw.text((x0 + 28, 138),
              f"轨迹  {row['step']:03d} / {row['total_steps']}",
              font=font(21), fill=white)

    bar_x0, bar_y0 = x0 + 28, 180
    bar_width = width - 56
    draw.rounded_rectangle((bar_x0, bar_y0, bar_x0 + bar_width, bar_y0 + 16),
                           radius=8, fill="#11171d")
    done_width = int(bar_width * row["step"] / row["total_steps"])
    if done_width:
        draw.rounded_rectangle((bar_x0, bar_y0, bar_x0 + done_width,
                                bar_y0 + 16), radius=8, fill=cyan)

    metrics = [
        ("几何更新", f"{row['update_ms']:.1f} ms", cyan),
        ("数据导出", f"{row['export_ms']:.1f} ms", white),
        ("几何管线", f"{row['pipeline_ms']:.1f} ms", white),
        ("当前面数", f"{row['faces']:,}", white),
        ("完成度", f"{row['completion_pct']:.1f}%", blue),
        ("累计去除", f"{row['removed_mm3']:.1f} mm³", white),
    ]
    y = 220
    for label, value, color in metrics:
        draw.text((x0 + 28, y), label, font=font(19), fill=muted)
        value_box = draw.textbbox((0, 0), value, font=font(21))
        value_width = value_box[2] - value_box[0]
        draw.text((x0 + width - 28 - value_width, y - 2), value,
                  font=font(21), fill=color)
        y += 40

    legend = [
        (blue, "剩余待去除"),
        (orange, "当前磨削区"),
        (red, "过磨警示"),
        (cyan, "计划边界"),
    ]
    # 图例采用两列布局，避免与上方“累计去除”指标和底部说明重叠。
    for index, (color, label) in enumerate(legend):
        column, row = index % 2, index // 2
        x = x0 + 28 + column * 156
        y = height - 132 + row * 30
        draw.ellipse((x, y + 4, x + 14, y + 18), fill=color)
        draw.text((x + 24, y), label, font=font(15), fill=white)

    draw.text((x0 + 28, height - 58), "真实 CT 肩胛骨 · 非临床仿真",
              font=font(15), fill=muted)


def render_dashboard(mesh, tool_segment, tool_radius, fraction, row, frame_path):
    """渲染整骨、盂面特写和指标面板组成的系统画面。"""
    raw_full = os.path.join(FRAMES, "_raw_full.png")
    raw_close = os.path.join(FRAMES, "_raw_close.png")

    # 零面积面不可见，显示副本中移除可避免法向计算警告，不改变计算网格。
    display_mesh = mesh.copy()
    display_mesh.update_faces(display_mesh.area_faces > 1e-12)
    display_mesh.remove_unreferenced_vertices()
    R.render_frame(display_mesh, tool_segment, tool_radius, raw_full,
                   frac=fraction, dpi=82, closeup=False)
    R.render_frame(display_mesh, tool_segment, tool_radius, raw_close,
                   frac=fraction, dpi=82, closeup=True)

    full = fit_image(R.postprocess(raw_full, (580, 520)), (580, 520))
    close = fit_image(R.postprocess(raw_close, (580, 520)), (580, 520))
    canvas = Image.new("RGB", (1540, 620), "#171d24")
    canvas.paste(full, (18, 70))
    canvas.paste(close, (576, 70))
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 18), "真实骨面全景", font=font(25), fill="#f4f7fa")
    draw.text((582, 18), "肩胛盂磨削特写", font=font(25), fill="#f4f7fa")
    draw_metric_panel(draw, row, 1168, 350, 620)
    draw.text((24, 590),
              "蓝=剩余  橙=当前磨削区域  红=过磨  青=计划边界  |  "
              "几何更新为实测；画面由 Matplotlib 离线录制",
              font=font(15), fill="#aab5c0")
    canvas.save(frame_path)
    os.remove(raw_full)
    os.remove(raw_close)


def build_keyframes(frame_paths):
    """从系统演示中抽取六张关键帧，生成论文和答辩可用拼图。"""
    positions = np.linspace(0, len(frame_paths) - 1, 6).round().astype(int)
    images = [Image.open(frame_paths[index]).convert("RGB") for index in positions]
    cells = [fit_image(image, (720, 290)) for image in images]
    canvas = Image.new("RGB", (1440, 870), "#171d24")
    for index, cell in enumerate(cells):
        x = (index % 2) * 720
        y = (index // 2) * 290
        canvas.paste(cell, (x, y))
    path = os.path.join(OUT, "真实骨面驻留式系统关键帧.png")
    canvas.save(path)
    return path


def main():
    global_start = time.perf_counter()
    os.makedirs(FRAMES, exist_ok=True)
    initial = trimesh.load(R.SCAP_STL)
    if not initial.is_watertight:
        raise RuntimeError("真实肩胛骨输入网格不水密")

    R.T_PLAN, R.N_PLAN = R.fit_glenoid_frame(initial)
    R.R_VIEW = trimesh.geometry.align_vectors(R.N_PLAN, [0, 0, 1])
    initial_volume = initial.volume
    cylinder, target, bounds = R.plan_solids()
    should_remove = (
        trimesh.boolean.intersection([initial, cylinder], engine="manifold").volume
        - trimesh.boolean.intersection([initial, target], engine="manifold").volume
    )
    trajectory = R.trajectory()
    capture_steps = selected_steps(trajectory)

    print(f"真实 CT 肩胛骨：{len(initial.faces)} 面，水密 {initial.is_watertight}")
    print(f"轨迹：{len(trajectory)} 步，演示抽帧：{len(capture_steps)} 帧")

    bone = to_manifold(initial)
    current_mesh = initial
    rows = []
    frame_paths = []

    initial_row = {
        "step": 0, "total_steps": len(trajectory), "phase": "初始",
        "tool_ms": 0.0, "update_ms": 0.0, "export_ms": 0.0,
        "metrics_ms": 0.0, "pipeline_ms": 0.0, "render_ms": 0.0,
        "faces": len(initial.faces), "removed_mm3": 0.0,
        "completion_pct": 0.0, "degenerate_faces": 0,
    }
    frame_path = os.path.join(FRAMES, "f0000.png")
    render_start = time.perf_counter()
    render_dashboard(initial, None, 0.0, 0.0, initial_row, frame_path)
    initial_row["render_ms"] = (time.perf_counter() - render_start) * 1000
    frame_paths.append(frame_path)

    for step, item in enumerate(trajectory, 1):
        pipeline_start = time.perf_counter()
        tool_start = time.perf_counter()
        phase, radius, p0, p1, tool = build_tool(item, bounds)
        tool_ms = (time.perf_counter() - tool_start) * 1000

        update_start = time.perf_counter()
        bone = bone - to_manifold(tool)
        face_count = bone.num_tri()  # 强制本步求值，保证计时真实。
        update_ms = (time.perf_counter() - update_start) * 1000

        export_start = time.perf_counter()
        current_mesh = to_trimesh(bone)
        export_ms = (time.perf_counter() - export_start) * 1000

        metrics_start = time.perf_counter()
        removed = initial_volume - bone.volume()
        completion = removed / should_remove * 100
        degenerate = int((current_mesh.area_faces <= 1e-12).sum())
        metrics_ms = (time.perf_counter() - metrics_start) * 1000
        pipeline_ms = (time.perf_counter() - pipeline_start) * 1000

        row = {
            "step": step, "total_steps": len(trajectory), "phase": phase,
            "tool_ms": tool_ms, "update_ms": update_ms,
            "export_ms": export_ms, "metrics_ms": metrics_ms,
            "pipeline_ms": pipeline_ms, "render_ms": 0.0,
            "faces": face_count, "removed_mm3": removed,
            "completion_pct": completion,
            "degenerate_faces": degenerate,
        }
        rows.append(row)

        if step in capture_steps:
            frame_path = os.path.join(FRAMES, f"f{step:04d}.png")
            render_start = time.perf_counter()
            render_dashboard(current_mesh, (p0, p1), radius,
                             step / len(trajectory), row, frame_path)
            row["render_ms"] = (time.perf_counter() - render_start) * 1000
            frame_paths.append(frame_path)
        if step % 20 == 0 or step == len(trajectory):
            print(f"  {step}/{len(trajectory)} | {phase} | 更新 {update_ms:.1f}ms | "
                  f"管线 {pipeline_ms:.1f}ms | {face_count} 面")

    if not current_mesh.is_watertight or not current_mesh.is_winding_consistent:
        raise RuntimeError("最终真实骨面未通过水密性或绕序检查")

    images = [Image.open(path).convert("RGB") for path in frame_paths]
    gif_path = os.path.join(OUT, "真实骨面驻留式系统演示.gif")
    images[0].save(gif_path, save_all=True, append_images=images[1:],
                   duration=GIF_MS, loop=0)
    keyframe_path = build_keyframes(frame_paths)
    mesh_path = os.path.join(OUT, "真实骨面驻留式最终网格.ply")
    current_mesh.export(mesh_path)

    csv_path = os.path.join(OUT, "resident_system_timing.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    update_times = np.asarray([row["update_ms"] for row in rows])
    pipeline_times = np.asarray([row["pipeline_ms"] for row in rows])
    render_times = np.asarray([
        row["render_ms"] for row in rows if row["render_ms"] > 0])
    beijing_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y-%m-%d %H:%M:%S")
    summary = (
        f"生成时间（北京时间）: {beijing_time}\n"
        f"数据: hill_sachs_001_F_37_R 真实 CT 肩胛骨\n"
        f"初始面数: {len(initial.faces)} | 最终面数: {len(current_mesh.faces)}\n"
        f"轨迹步数: {len(trajectory)} | 演示帧数: {len(frame_paths)}\n"
        f"完成度: {rows[-1]['completion_pct']:.2f}% | "
        f"去除体积: {rows[-1]['removed_mm3']:.6f}mm³\n"
        f"几何更新: 平均 {update_times.mean():.1f}ms | "
        f"P95 {np.percentile(update_times, 95):.1f}ms | "
        f"最大 {update_times.max():.1f}ms\n"
        f"几何管线（工具+更新+导出+指标）: 平均 {pipeline_times.mean():.1f}ms | "
        f"P95 {np.percentile(pipeline_times, 95):.1f}ms | "
        f"最大 {pipeline_times.max():.1f}ms | "
        f"超过33.3ms {int((pipeline_times > 33.3).sum())}步\n"
        f"Matplotlib录制渲染: 平均 {render_times.mean():.0f}ms/帧（非实时）\n"
        f"零面积三角形: {rows[-1]['degenerate_faces']}\n"
        f"最终水密: {current_mesh.is_watertight} | "
        f"绕序一致: {current_mesh.is_winding_consistent}\n"
        f"总运行时间: {time.perf_counter() - global_start:.1f}s\n"
    )
    summary_path = os.path.join(OUT, "resident_system_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as file:
        file.write(summary)
    print("\n" + summary)
    print("演示：", gif_path)
    print("关键帧：", keyframe_path)


if __name__ == "__main__":
    main()
