# -*- coding: utf-8 -*-
"""
E5-lite：manifold3d 内核驻留式增量更新
========================================
对比两条使用同一 manifold3d 布尔内核的 CPU 路线：
  ① 基线：每步 Trimesh -> Manifold -> 布尔 -> Trimesh；
  ② 驻留：骨网格始终保留为 Manifold，只转换当步工具，最终再导出 Trimesh。

本实验先量化数据往返和重复三角化的成本，为后续真正的局部区域更新建立
更干净、更快的 CPU 基线。两条路线逐步对拍去除体积，并检查最终水密性。
"""
import argparse
import csv
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import matplotlib
import numpy as np
import trimesh
from matplotlib import font_manager
from manifold3d import Manifold, Mesh

matplotlib.use("Agg")
# 优先直接加载 Windows 中文字体，避免无桌面环境下字体发现失败。
CHINESE_FONT = r"C:\Windows\Fonts\msyh.ttc"
if os.path.exists(CHINESE_FONT):
    font_manager.fontManager.addfont(CHINESE_FONT)
    chinese_font_name = font_manager.FontProperties(fname=CHINESE_FONT).get_name()
    matplotlib.rcParams["font.family"] = chinese_font_name
    matplotlib.rcParams["font.sans-serif"] = [chinese_font_name, "DejaVu Sans"]
else:
    matplotlib.rcParams["font.sans-serif"] = ["DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(OUT, "..", "真实骨模型演示"))
import real_bone_demo as R  # noqa: E402

VOLUME_TOLERANCE = 1e-2     # 逐步去除体积允许偏差（mm³）
GEOMETRY_SAMPLES = 20000    # 双向表面距离每侧固定采样数

# Windows 终端默认 GBK 无法输出“mm³”，统一改为 UTF-8，保证实验日志可读。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _to_manifold(mesh):
    """把 Trimesh 转成 manifold3d 网格，顶点精度与 trimesh 后端保持一致。"""
    return Manifold(mesh=Mesh(
        vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
        tri_verts=np.asarray(mesh.faces, dtype=np.uint32),
    ))


def _to_trimesh(manifold):
    """把最终 manifold3d 网格导出为不自动重处理的 Trimesh。"""
    mesh = manifold.to_mesh()
    return trimesh.Trimesh(
        vertices=mesh.vert_properties,
        faces=mesh.tri_verts,
        process=False,
    )


def _build_tool(item, bounds):
    """根据一段计划轨迹构造受触觉边界限制的世界坐标工具扫掠体。"""
    name, radius, p0_plan, p1_plan = item
    p0, p1 = R.to_world(p0_plan), R.to_world(p1_plan)
    tool = trimesh.boolean.intersection(
        [R.sweep_capsule(radius, p0, p1), bounds[name]],
        engine="manifold",
    )
    return name, tool


def _run_roundtrip(initial, trajectory, bounds):
    """运行每步都进出 manifold3d 的原始 Trimesh 基线。"""
    bone = initial.copy()
    initial_volume = bone.volume
    rows = []
    for step, item in enumerate(trajectory, 1):
        name, tool = _build_tool(item, bounds)
        start = time.perf_counter()
        bone = trimesh.boolean.difference([bone, tool], engine="manifold")
        elapsed_ms = (time.perf_counter() - start) * 1000
        rows.append({
            "step": step,
            "phase": name,
            "roundtrip_ms": elapsed_ms,
            "roundtrip_faces": len(bone.faces),
            "roundtrip_removed_mm3": initial_volume - bone.volume,
        })
        if step % 20 == 0 or step == len(trajectory):
            print(f"  基线 {step}/{len(trajectory)} | {elapsed_ms:.1f}ms | "
                  f"{len(bone.faces)} 面")
    return bone, rows


def _run_resident(initial, trajectory, bounds):
    """运行骨网格常驻 manifold3d 的增量布尔路线。"""
    bone = _to_manifold(initial)
    initial_volume = bone.volume()
    rows = []
    for step, item in enumerate(trajectory, 1):
        name, tool = _build_tool(item, bounds)
        start = time.perf_counter()
        tool_manifold = _to_manifold(tool)
        bone = bone - tool_manifold
        face_count = bone.num_tri()  # 强制本步求值，避免惰性表达式造成虚假计时
        elapsed_ms = (time.perf_counter() - start) * 1000
        rows.append({
            "resident_ms": elapsed_ms,
            "resident_faces": face_count,
            "resident_removed_mm3": initial_volume - bone.volume(),
        })
        if step % 20 == 0 or step == len(trajectory):
            print(f"  驻留 {step}/{len(trajectory)} | {elapsed_ms:.1f}ms | "
                  f"{face_count} 面")
    return bone, rows


def _write_plot(rows):
    """绘制逐步耗时与网格面数对比图。"""
    steps = np.asarray([row["step"] for row in rows])
    roundtrip_ms = np.asarray([row["roundtrip_ms"] for row in rows])
    resident_ms = np.asarray([row["resident_ms"] for row in rows])
    roundtrip_faces = np.asarray([row["roundtrip_faces"] for row in rows])
    resident_faces = np.asarray([row["resident_faces"] for row in rows])

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(steps, roundtrip_ms, label="Trimesh 往返基线", linewidth=1.5)
    axes[0].plot(steps, resident_ms, label="Manifold 内核驻留", linewidth=1.5)
    axes[0].axhline(33.3, color="#777777", linestyle="--", linewidth=1,
                    label="30 Hz：33.3 ms")
    axes[0].set_ylabel("单步更新耗时（ms）")
    axes[0].grid(alpha=0.25)
    axes[0].legend()

    axes[1].plot(steps, roundtrip_faces, label="Trimesh 往返基线",
                 linewidth=1.5)
    axes[1].plot(steps, resident_faces, label="Manifold 内核驻留",
                 linewidth=1.5)
    axes[1].set_xlabel("轨迹步")
    axes[1].set_ylabel("三角形面数")
    axes[1].grid(alpha=0.25)
    axes[1].legend()
    fig.suptitle("E5-lite：内核驻留式增量更新性能对比")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "e5lite_性能对比.png"), dpi=160)
    plt.close(fig)


def _surface_distance_stats(mesh_a, mesh_b):
    """固定随机种子计算两网格的双向采样表面距离统计。"""
    mesh_a = mesh_a.copy()
    mesh_b = mesh_b.copy()
    mesh_a.update_faces(mesh_a.area_faces > 1e-12)
    mesh_b.update_faces(mesh_b.area_faces > 1e-12)
    mesh_a.remove_unreferenced_vertices()
    mesh_b.remove_unreferenced_vertices()
    points_a, _ = trimesh.sample.sample_surface(
        mesh_a, GEOMETRY_SAMPLES, seed=0)
    points_b, _ = trimesh.sample.sample_surface(
        mesh_b, GEOMETRY_SAMPLES, seed=1)
    _, distance_ab, _ = trimesh.proximity.closest_point(mesh_b, points_a)
    _, distance_ba, _ = trimesh.proximity.closest_point(mesh_a, points_b)
    distances = np.concatenate([distance_ab, distance_ba])
    return {
        "mean": float(distances.mean()),
        "p95": float(np.percentile(distances, 95)),
        "max": float(distances.max()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="E5-lite 内核驻留增量实验")
    parser.add_argument("--steps", type=int, default=None,
                        help="只运行前 N 步；默认运行完整轨迹")
    parser.add_argument("--no-write", action="store_true",
                        help="只打印结果，不写 CSV、摘要和图片")
    args = parser.parse_args(argv)

    initial = trimesh.load(R.SCAP_STL)
    if not initial.is_watertight:
        raise RuntimeError("输入肩胛骨网格不水密")
    R.T_PLAN, R.N_PLAN = R.fit_glenoid_frame(initial)
    _, _, bounds = R.plan_solids()
    trajectory = R.trajectory()
    if args.steps is not None:
        if args.steps < 1:
            parser.error("--steps 必须大于 0")
        trajectory = trajectory[:args.steps]

    print(f"模型 {len(initial.faces)} 面 | 本次轨迹 {len(trajectory)} 步")
    print("\n[基线] Trimesh 每步进出 manifold3d ...")
    roundtrip, rows = _run_roundtrip(initial, trajectory, bounds)
    print("\n[优化] 骨网格常驻 manifold3d ...")
    resident_manifold, resident_rows = _run_resident(initial, trajectory, bounds)
    resident = _to_trimesh(resident_manifold)

    for row, resident_row in zip(rows, resident_rows):
        row.update(resident_row)
        row["volume_delta_mm3"] = abs(
            row["roundtrip_removed_mm3"] - row["resident_removed_mm3"])
        row["speedup"] = row["roundtrip_ms"] / row["resident_ms"]
    max_volume_delta = max(row["volume_delta_mm3"] for row in rows)
    if max_volume_delta > VOLUME_TOLERANCE:
        raise RuntimeError(
            f"最大逐步体积偏差 {max_volume_delta:.6f} mm³ 超过 "
            f"{VOLUME_TOLERANCE} mm³")
    if not resident.is_watertight or not resident.is_winding_consistent:
        raise RuntimeError("驻留路线最终网格未通过水密性或绕序检查")
    distance_stats = _surface_distance_stats(roundtrip, resident)

    roundtrip_ms = np.asarray([row["roundtrip_ms"] for row in rows])
    resident_ms = np.asarray([row["resident_ms"] for row in rows])
    speedup = roundtrip_ms.mean() / resident_ms.mean()
    resident_p95 = float(np.percentile(resident_ms, 95))
    resident_over_budget = int((resident_ms > 33.3).sum())
    roundtrip_degenerate = int((roundtrip.area_faces <= 1e-12).sum())
    resident_degenerate = int((resident.area_faces <= 1e-12).sum())
    beijing_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y-%m-%d %H:%M:%S")
    summary = (
        f"生成时间（北京时间）: {beijing_time}\n"
        f"E5-lite manifold3d 内核驻留式增量更新\n"
        f"轨迹步数: {len(trajectory)}\n"
        f"Trimesh往返基线: 平均 {roundtrip_ms.mean():.1f}ms / "
        f"最大 {roundtrip_ms.max():.1f}ms / 最终 {len(roundtrip.faces)} 面\n"
        f"Manifold内核驻留: 平均 {resident_ms.mean():.1f}ms / "
        f"P95 {resident_p95:.1f}ms / 最大 {resident_ms.max():.1f}ms / "
        f"超过33.3ms {resident_over_budget}步 / 最终 {len(resident.faces)} 面\n"
        f"端到端加速比: {speedup:.2f}x\n"
        f"最终去除体积: 基线 {rows[-1]['roundtrip_removed_mm3']:.6f}mm³ / "
        f"驻留 {rows[-1]['resident_removed_mm3']:.6f}mm³\n"
        f"最大逐步体积偏差: {max_volume_delta:.6f}mm³\n"
        f"双向表面距离（{GEOMETRY_SAMPLES}点/侧）: "
        f"均值 {distance_stats['mean']:.6f}mm / "
        f"P95 {distance_stats['p95']:.6f}mm / "
        f"最大 {distance_stats['max']:.6f}mm\n"
        f"零面积三角形: 基线 {roundtrip_degenerate} / "
        f"驻留 {resident_degenerate}\n"
        f"驻留路线最终水密: {resident.is_watertight}\n"
    )
    print("\n" + summary)

    if not args.no_write:
        with open(os.path.join(OUT, "e5lite_timing.csv"), "w", newline="",
                  encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        with open(os.path.join(OUT, "e5lite_summary.txt"), "w",
                  encoding="utf-8") as file:
            file.write(summary)
        # PLY 保留共享顶点索引；STL 会把每个三角形顶点拆开，不用于拓扑复核。
        resident.export(os.path.join(OUT, "e5lite_驻留最终网格.ply"))
        _write_plot(rows)


if __name__ == "__main__":
    main()
