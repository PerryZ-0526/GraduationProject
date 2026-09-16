# -*- coding: utf-8 -*-
"""
最小可看结果工作流：骨磨削表面增量更新与状态可视化（CPU 保底管线）
=================================================================
对应 16 号《毕业导向的三工作实施方案》的三工作 MVP 初步验证：
  工作一（算法层）：磨钻扫掠体（直线段=胶囊体，球磨解析扫掠）与骨面的
                   布尔减法增量更新（trimesh + manifold3d，CPU 精确布尔）
  工作二（系统层）：更新全流程的逐步渲染与性能记录（单步布尔耗时、面数增长）
  工作三（验证层）：剩余磨削量（蓝）/过磨（黄红）着色、体积完成度、
                   剩余脊高与过磨深度统计
输出：快照 PNG、指标 CSV、指标图、控制台摘要（均在脚本所在目录）
"""
import os
import time
import csv

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")  # 无显示器环境，离屏渲染
matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "DejaVu Sans"]  # 中文渲染
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Patch

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------- 场景参数（单位：mm） ----------------
BONE_W, BONE_D, BONE_H = 40.0, 40.0, 8.0   # 骨块（长方体基座）
BUMP_R, BUMP_H = 12.0, 3.2                 # 骨面凸起（模拟肩胛盂关节面）
CX, CY = BONE_W / 2, BONE_D / 2            # 计划区中心
PLAN_Z = BONE_H                            # 计划目标平面 z = 8
PLAN_R = 13.0                              # 计划去除区半径
BURR_R = 3.0                               # 球形磨钻半径
PASS1_Z = PLAN_Z + BURR_R + 0.7            # 粗磨：球心高度（留约 0.7mm 余量）
PASS2_Z = PLAN_Z + BURR_R - 0.05           # 精磨：球心高度（过磨 0.05mm，演示告警）
GRIND_R = 12.3                             # 扫掠覆盖半径（盖住凸起）
ROW_STEP = 2.4                             # 井字路径行距
SEG_STEP = 4.0                             # 单段扫掠长度（一个布尔运算）

BONE_COLOR = np.array([0.86, 0.78, 0.66])  # 骨面底色（米色）


# ---------------- 场景构建 ----------------
def make_bone():
    """初始骨面：长方体基座 ∪ 顶部压扁球冠（凸起的关节面），水密实体"""
    slab = trimesh.creation.box(extents=[BONE_W, BONE_D, BONE_H])
    slab.apply_translation([CX, CY, BONE_H / 2])
    bump = trimesh.creation.icosphere(subdivisions=3, radius=BUMP_R)
    # 各向异性缩放（scale_matrix 仅支持标量，故手写 4x4 矩阵）：z 向压扁为球冠
    S = np.eye(4)
    S[2, 2] = BUMP_H / BUMP_R
    bump.apply_transform(S)
    bump.apply_translation([CX, CY, BONE_H])
    return trimesh.boolean.union([slab, bump], engine="manifold")


def make_plan_cylinder(z0, z1):
    """计划区圆柱（z0~z1），用于计算应去除/过磨体积"""
    cyl = trimesh.creation.cylinder(radius=PLAN_R, sections=64,
                                    segment=[[CX, CY, z0], [CX, CY, z1]])
    return cyl


def grinding_segments(pass_z):
    """生成井字形扫掠段列表 [(p0, p1), ...]，奇数行反向（弓形走刀）"""
    segs = []
    n_rows = int(2 * GRIND_R / ROW_STEP)
    ys = np.linspace(CY - GRIND_R, CY + GRIND_R, n_rows)
    for i, y in enumerate(ys):
        dy = y - CY
        half = np.sqrt(max(GRIND_R ** 2 - dy ** 2, 1e-6))
        x0, x1 = CX - half, CX + half
        if i % 2 == 1:  # 奇数行反向，模拟弓形连续走刀
            x0, x1 = x1, x0
        L = abs(x1 - x0)
        n_seg = max(int(L / SEG_STEP), 1)
        xs = np.linspace(x0, x1, n_seg + 1)
        for j in range(n_seg):
            segs.append(((xs[j], y, pass_z), (xs[j + 1], y, pass_z)))
    return segs


def sweep_capsule(p0, p1):
    """单段扫掠体：胶囊体 = 球磨沿直线段的精确扫掠（解析球面）"""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    L = float(np.linalg.norm(d))
    if L < 1e-9:  # 退化为球
        cap = trimesh.creation.icosphere(subdivisions=3, radius=BURR_R)
        cap.apply_translation(p0)
        return cap
    cap = trimesh.creation.capsule(radius=BURR_R, height=L, count=(8, 16))
    cap.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], d))
    cap.apply_translation((p0 + p1) / 2)
    return cap


# ---------------- 工作三：状态着色与统计 ----------------
def face_colors(mesh, dz_max_show=1.0):
    """面着色：计划区内 z>PLAN_Z=剩余（蓝），z<PLAN_Z=过磨（黄红），区外骨色"""
    tri = mesh.vertices[mesh.faces]
    cen = tri.mean(axis=1)                    # 面质心
    n = mesh.face_normals
    light = np.array([0.35, 0.25, 0.90]); light /= np.linalg.norm(light)
    shade = 0.45 + 0.55 * np.clip(n @ light, 0, 1)  # 简单 Lambert 光照

    colors = np.tile(BONE_COLOR, (len(cen), 1))
    r = np.hypot(cen[:, 0] - CX, cen[:, 1] - CY)
    inside = r < PLAN_R
    dz = cen[:, 2] - PLAN_Z
    rem = inside & (dz > 0)                   # 剩余材料
    over = inside & (dz <= 0)                 # 过磨
    if rem.any():
        t = np.clip(dz[rem] / dz_max_show, 0, 1)
        colors[rem] = plt.cm.Blues(0.35 + 0.55 * t)[:, :3]
    if over.any():
        t = np.clip(-dz[over] / 0.3, 0, 1)    # 0.3mm 内从黄到红
        colors[over] = np.stack([np.ones_like(t), 0.85 - 0.85 * t,
                                 0.25 - 0.25 * t], axis=1)
    colors = np.clip(colors * shade[:, None], 0, 1)
    return colors


def surface_stats(mesh):
    """计划区内顶点相对计划面的偏差统计（剩余脊高 / 过磨深度）"""
    v = mesh.vertices
    r = np.hypot(v[:, 0] - CX, v[:, 1] - CY)
    dz = v[r < PLAN_R, 2] - PLAN_Z
    return float(dz.max()), float(dz.min()), dz


# ---------------- 工作二：渲染 ----------------
def render(mesh, title, png, max_faces=30000):
    """三维渲染当前骨面 + 计划圆盘，保存 PNG"""
    fig = plt.figure(figsize=(9.5, 7))
    ax = fig.add_subplot(111, projection="3d")

    idx = np.arange(len(mesh.faces))
    if len(idx) > max_faces:  # 显示用面下采样（指标统计用全量）
        idx = np.random.default_rng(0).choice(idx, max_faces, replace=False)
    tri = mesh.vertices[mesh.faces[idx]]
    colors = face_colors(mesh)[idx]
    pc = Poly3DCollection(tri, facecolors=colors, edgecolor="none")
    ax.add_collection3d(pc)

    # 计划目标面（半透明圆盘，扇形三角化）
    th = np.linspace(0, 2 * np.pi, 64)
    ring = np.stack([CX + PLAN_R * np.cos(th), CY + PLAN_R * np.sin(th),
                     np.full_like(th, PLAN_Z)], axis=1)          # (64,3)
    center = np.array([CX, CY, PLAN_Z])
    disk_tri = [np.array([center, ring[k], ring[k + 1]]) for k in range(63)]
    ax.add_collection3d(Poly3DCollection(disk_tri, facecolors=(0.2, 0.2, 0.2, 0.15),
                                         edgecolor="none"))

    ax.set_xlim(0, BONE_W); ax.set_ylim(0, BONE_D); ax.set_zlim(0, 12.5)
    ax.set_box_aspect((BONE_W, BONE_D, 12.5))
    ax.view_init(elev=28, azim=-60)
    ax.set_title(title, fontsize=12)
    ax.legend(handles=[Patch(color=plt.cm.Blues(0.7), label="剩余待去除材料"),
                       Patch(color=(1.0, 0.6, 0.15), label="过磨区域"),
                       Patch(color=BONE_COLOR, label="计划区外骨面"),
                       Patch(color=(0.4, 0.4, 0.4), label="计划目标面")],
              loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, png), dpi=110)
    plt.close(fig)


# ---------------- 主流程 ----------------
def main():
    print("[1/5] 构建初始骨面 ...")
    bone = make_bone()
    v0 = bone.volume
    # 应去除体积 = 初始骨面在计划圆柱(z>PLAN_Z)内的体积
    should = trimesh.boolean.intersection(
        [bone, make_plan_cylinder(PLAN_Z, PLAN_Z + 12)], engine="manifold").volume
    print(f"      初始体积 {v0:.1f} mm³，计划应去除 {should:.1f} mm³，初始面数 {len(bone.faces)}")
    render(bone, "步骤 0 | 初始骨面（含凸起关节面）与计划目标面", "snapshot_0_initial.png")

    rows = []          # 指标记录：pass, step, faces, removed, time_ms
    snapshots = []     # (mesh引用需拷贝，仅存参数) —— 用深拷贝太重，改为定点重渲染
    t_total = 0.0

    print("[2/5] 粗磨（留余量） ...")
    segs1 = grinding_segments(PASS1_Z)
    bone, t_total = run_pass(bone, "粗磨", segs1, rows, t_total,
                             v0, should, snap_frac=(0.5, 1.0))
    print("[3/5] 精磨（至计划面，含轻微过磨演示） ...")
    segs2 = grinding_segments(PASS2_Z)
    bone, t_total = run_pass(bone, "精磨", segs2, rows, t_total,
                             v0, should, snap_frac=(1.0,))

    print("[4/5] 统计与指标图 ...")
    rem_max, over_min, dz = surface_stats(bone)
    vf = bone.volume
    removed = v0 - vf
    done = removed / should
    # 过磨体积 = 计划圆柱(z<PLAN_Z)内被去除的体积
    cyl_below = make_plan_cylinder(PLAN_Z - 6, PLAN_Z)
    v_below_init = trimesh.boolean.intersection(
        [make_bone(), cyl_below], engine="manifold").volume
    v_below_final = trimesh.boolean.intersection(
        [bone, cyl_below], engine="manifold").volume
    overcut_vol = v_below_init - v_below_final

    # 渲染最终状态
    render(bone,
           f"最终 | 已去除 {removed:.1f} mm³（完成度 {done*100:.1f}%）"
           f" | 剩余脊高 {rem_max:.2f} mm，过磨深度 {max(-over_min,0):.2f} mm",
           "snapshot_final.png")

    # 指标 CSV
    with open(os.path.join(OUT, "metrics.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pass", "step", "faces", "removed_mm3", "boolean_ms"])
        w.writerows(rows)

    # 指标图：去除体积曲线 + 单步耗时 + 顶点偏差直方图
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    steps = np.arange(1, len(rows) + 1)
    axes[0].plot(steps, [r[3] for r in rows], "-o", ms=2, color="tab:blue")
    axes[0].set_xlabel("布尔步数"); axes[0].set_ylabel("累积去除体积 (mm³)")
    axes[0].set_title(f"完成度 {done*100:.1f}%（应去除 {should:.0f} mm³）")
    axes[1].plot(steps, [r[4] for r in rows], "-", color="tab:red")
    axes[1].set_xlabel("布尔步数"); axes[1].set_ylabel("单步布尔耗时 (ms)")
    axes[1].set_title(f"总耗时 {t_total:.1f} s，最终面数 {len(bone.faces)}")
    axes[2].hist(dz, bins=80, color="tab:gray")
    axes[2].axvline(0, color="k", ls="--", lw=1)
    axes[2].set_xlabel("表面相对计划面偏差 (mm)")
    axes[2].set_title(f"剩余脊高 {rem_max:.2f} / 过磨 {max(-over_min,0):.2f} mm")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "metrics.png"), dpi=110)
    plt.close(fig)

    print("[5/5] 摘要")
    summary = (
        f"初始体积: {v0:.1f} mm3\n"
        f"计划应去除: {should:.1f} mm3\n"
        f"实际去除: {removed:.1f} mm3 (完成度 {done*100:.1f}%)\n"
        f"过磨体积: {overcut_vol:.2f} mm3\n"
        f"剩余脊高(顶点最大偏差): {rem_max:.3f} mm\n"
        f"过磨深度(顶点最小偏差): {over_min:.3f} mm\n"
        f"最终面数: {len(bone.faces)}\n"
        f"布尔总步数: {len(rows)}, 总耗时: {t_total:.1f} s, "
        f"平均单步: {t_total/len(rows)*1000:.0f} ms\n"
        f"水密性: {bone.is_watertight}"
    )
    print(summary)
    with open(os.path.join(OUT, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary + "\n")
    print("完成。输出目录：", OUT)


def run_pass(bone, name, segs, rows, t_total, v0, should, snap_frac):
    """执行一遍扫掠：逐段布尔减法 + 记录 + 定点快照"""
    n = len(segs)
    snap_ids = {max(int(n * f), 1) - 1 for f in snap_frac}
    for i, (p0, p1) in enumerate(segs):
        tool = sweep_capsule(p0, p1)
        t0 = time.perf_counter()
        bone = trimesh.boolean.difference([bone, tool], engine="manifold")
        dt = (time.perf_counter() - t0) * 1000
        t_total += dt / 1000
        rows.append([name, i + 1, len(bone.faces), v0 - bone.volume, round(dt, 1)])
        if i in snap_ids:
            removed = v0 - bone.volume
            render(bone,
                   f"{name} 第 {i+1}/{n} 段 | 已去除 {removed:.1f} mm³"
                   f"（完成度 {removed/should*100:.1f}%）| 面数 {len(bone.faces)}",
                   f"snapshot_{name}_{i+1}.png")
        if (i + 1) % 10 == 0:
            print(f"      {name} {i+1}/{n} 面数 {len(bone.faces)} 耗时 {dt:.0f}ms")
    return bone, t_total


if __name__ == "__main__":
    main()
