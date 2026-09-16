# -*- coding: utf-8 -*-
"""
骨表面增量更新与实时实现：动态演示（CPU 实时循环版）
====================================================
对应 16 号三工作：工作一（增量更新：扫掠体布尔）+ 工作二（实时实现：
逐帧更新-渲染循环与帧耗时实测）。在课题规划与专题调研目录的 13 号验证管线之上新增：
  1. 实时循环：每段扫掠 -> 布尔增量更新 -> 受影响区域统计 -> 着色渲染
  2. 帧耗时实测：单帧 = 更新耗时 + 渲染耗时，给出等效帧率（实时性证明）
  3. 磨钻位置显示：当前扫掠段处绘制半透明红色球磨
  4. 输出动画 GIF（骨面被逐步切削的完整过程）与关键帧拼图
复用 13 号报告对应 workflow_demo.py 的场景与更新函数（同目录导入）。
"""
import os
import time
import csv

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
# 中文渲染：沙盒内可用 Noto Sans CJK（无则回退 DejaVu）
matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image

from workflow_demo import (make_bone, grinding_segments, sweep_capsule, face_colors,
                           BONE_W, BONE_D, PLAN_Z, PLAN_R, BURR_R, CX, CY,
                           PASS1_Z, PASS2_Z, BONE_COLOR)

OUT = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(OUT, "frames")
os.makedirs(FRAMES, exist_ok=True)

GIF_MS = 80          # GIF 每帧播放时长（ms）


def affected_count(mesh, p0, p1, margin=1.0):
    """估计本步受影响面数：面质心距扫掠轴 < 球半径+margin 的面
    （E5 将只对这部分做局部处理，此处用于展示更新的局部性）"""
    tri = mesh.vertices[mesh.faces]
    cen = tri.mean(axis=1)
    a, b = np.asarray(p0, float), np.asarray(p1, float)
    ab = b - a
    L2 = float(ab @ ab)
    t = np.clip(((cen - a) @ ab) / (L2 + 1e-12), 0, 1)[:, None]
    d = np.linalg.norm(cen - (a + t * ab), axis=1)
    return int((d < BURR_R + margin).sum())


def render_frame(mesh, tool_center, title, path, dpi=72):
    """渲染单帧：骨面着色 + 计划圆盘 + 当前球磨位置"""
    fig = plt.figure(figsize=(6.4, 4.8))
    ax = fig.add_subplot(111, projection="3d")

    tri = mesh.vertices[mesh.faces]
    pc = Poly3DCollection(tri, facecolors=face_colors(mesh), edgecolor="none")
    ax.add_collection3d(pc)

    # 计划目标面（半透明圆盘）
    th = np.linspace(0, 2 * np.pi, 48)
    ring = np.stack([CX + PLAN_R * np.cos(th), CY + PLAN_R * np.sin(th),
                     np.full_like(th, PLAN_Z)], axis=1)
    c = np.array([CX, CY, PLAN_Z])
    disk = [np.array([c, ring[k], ring[k + 1]]) for k in range(47)]
    ax.add_collection3d(Poly3DCollection(disk, facecolors=(0.2, 0.2, 0.2, 0.15),
                                         edgecolor="none"))
    # 当前磨钻（半透明红球）
    burr = trimesh.creation.icosphere(subdivisions=2, radius=BURR_R)
    burb_tri = np.asarray(burr.triangles) + np.asarray(tool_center) - burr.vertices.mean(0)
    ax.add_collection3d(Poly3DCollection(burb_tri, facecolors=(0.9, 0.15, 0.1, 0.30),
                                         edgecolor="none"))

    ax.set_xlim(0, BONE_W); ax.set_ylim(0, BONE_D); ax.set_zlim(0, 12.5)
    ax.set_box_aspect((BONE_W, BONE_D, 12.5))
    ax.view_init(elev=28, azim=-60)
    ax.set_title(title, fontsize=8)
    ax.set_axis_off()
    fig.tight_layout(pad=0.2)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def main():
    print("[1/4] 构建场景 ...")
    bone = make_bone()
    v0 = bone.volume
    should = trimesh.boolean.intersection(
        [bone, trimesh.creation.cylinder(
            radius=PLAN_R, sections=48,
            segment=[[CX, CY, PLAN_Z], [CX, CY, PLAN_Z + 12]])],
        engine="manifold").volume

    frames = []
    rows = []  # pass, step, t_bool_ms, t_render_ms, faces, affected, removed
    t_bools, t_frames = [], []

    # 第 0 帧（初始状态，磨钻悬停在起点上方）
    p0_first = grinding_segments(PASS1_Z)[0][0]
    render_frame(bone, p0_first, "初始骨面 | 蓝色=待去除 凸起关节面",
                 os.path.join(FRAMES, "f0000.png"))
    frames.append("f0000.png")

    print("[2/4] 实时更新循环（粗磨+精磨）...")
    fid = 1
    for name, pz in [("粗磨", PASS1_Z), ("精磨", PASS2_Z)]:
        segs = grinding_segments(pz)
        for i, (p0, p1) in enumerate(segs):
            tool = sweep_capsule(p0, p1)
            t0 = time.perf_counter()
            bone = trimesh.boolean.difference([bone, tool], engine="manifold")
            t_bool = (time.perf_counter() - t0) * 1000
            t_bools.append(t_bool)

            na = affected_count(bone, p0, p1)
            removed = v0 - bone.volume
            pct = removed / should * 100

            t0 = time.perf_counter()
            fn = f"f{fid:04d}.png"
            render_frame(bone, (np.asarray(p0) + np.asarray(p1)) / 2,
                         f"{name} {i+1}/{len(segs)} | 去除 {removed:.0f}mm³"
                         f"({pct:.0f}%) | 更新 {t_bool:.0f}ms | 受影响 {na}/{len(bone.faces)} 面",
                         os.path.join(FRAMES, fn))
            t_render = (time.perf_counter() - t0) * 1000
            t_frames.append(t_bool + t_render)
            frames.append(fn)
            rows.append([name, i + 1, round(t_bool, 1), round(t_render, 1),
                         len(bone.faces), na, round(removed, 1)])
            fid += 1
        print(f"      {name} 完成：{len(segs)} 段")

    print("[3/4] 合成 GIF 动画 ...")
    imgs = [Image.open(os.path.join(FRAMES, f)) for f in frames]
    gif_path = os.path.join(OUT, "骨面增量更新实时演示.gif")
    imgs[0].save(gif_path, save_all=True, append_images=imgs[1:],
                 duration=GIF_MS, loop=0)

    # 关键帧拼图（6 帧横排）
    picks = [frames[0], frames[len(frames) // 4], frames[len(frames) // 2],
             frames[3 * len(frames) // 4], frames[-2], frames[-1]]
    fig, axes = plt.subplots(1, 6, figsize=(22, 3.6))
    for ax, f in zip(axes, picks):
        ax.imshow(Image.open(os.path.join(FRAMES, f)))
        ax.axis("off")
    fig.suptitle("骨表面增量更新过程关键帧（蓝=剩余待去除，黄红=过磨，红球=磨钻）", fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "关键帧拼图.png"), dpi=100)
    plt.close(fig)

    print("[4/4] 实时性统计 ...")
    t_bools, t_frames = np.array(t_bools), np.array(t_frames)
    summary = (
        f"布尔总步数: {len(t_bools)}\n"
        f"单步布尔更新: 平均 {t_bools.mean():.1f} ms / 最大 {t_bools.max():.1f} ms "
        f"-> 纯更新等效 {1000/t_bools.mean():.0f} fps\n"
        f"单帧（更新+渲染）: 平均 {t_frames.mean():.0f} ms / 最大 {t_frames.max():.0f} ms "
        f"-> 等效 {1000/t_frames.mean():.1f} fps\n"
        f"实时判据（30fps=33ms/帧，仅更新口径）: "
        f"{'达标' if t_bools.mean() < 33 else '未达标'}\n"
        f"最终面数: {len(bone.faces)}，水密: {bone.is_watertight}\n"
        f"GIF 帧数: {len(frames)}，播放速度 {GIF_MS} ms/帧"
    )
    print(summary)
    with open(os.path.join(OUT, "realtime_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary + "\n")
    with open(os.path.join(OUT, "realtime_timing.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pass", "step", "t_bool_ms", "t_render_ms", "faces", "affected", "removed_mm3"])
        w.writerows(rows)
    print("完成。输出：", OUT)


if __name__ == "__main__":
    main()
