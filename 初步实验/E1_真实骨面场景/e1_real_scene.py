# -*- coding: utf-8 -*-
"""
E1 真实骨面场景实验（解析兜底几何版）
=====================================
按课题规划与专题调研目录的 14 号 E1 设计构建"真实形态"场景并裸跑更新管线：
  场景：凹形肩胛盂关节面（真实盂为凹面，反肩手术将其磨平）+ 低频表面噪声
  计划：倾斜非平面计划面（倾角/后倾角 + 中央凸台 boss + 中央柱 post，按 Perform
        基板规格），偏差度量用计划面法向坐标 s 而非 z 差
  轨迹：五相位（面粗/面精/台粗/台精/柱钻），扫掠体沿计划面坐标系生成
  验证：拓扑健康断言、完成度、剩余/过磨法向偏差统计、退化事件监测
数据源说明：A 级（TotalSegmentator+CT）与 B 级（BodyParts3D）暂不可达
（BodyParts3D 失联、NIH 3D 为 JS 站），本版为 C 级解析兜底；骨面输入为标准
网格接口，后续可直接替换真实 CT 网格。
"""
import os
import time
import csv

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image

OUT = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(OUT, "frames")
os.makedirs(FRAMES, exist_ok=True)
GIF_MS = 90

# ---------------- 场景参数（mm / 度） ----------------
Z_TOP = 12.0                    # 骨块顶面（关节面所在平面）
CUP_A, CUP_B, CUP_C = 12.0, 14.0, 3.0   # 盂窝椭球半轴（凹面）
CUP_LIFT = 1.0                  # 椭球中心抬高量（决定窝深 = CUP_C - CUP_LIFT = 2）
TILT_I, TILT_V = 6.0, 5.0       # 计划面倾角(绕x)/后倾角(绕y)
C_Z = Z_TOP - 2.2               # 计划面中心高度（含安全余量，见报告）
R_PLATE, R_BOSS, R_POST = 12.5, 5.5, 2.5   # 基板/凸台/柱半径（Perform 规格）
POST_TOOL_R = 2.9               # 柱钻工具半径（略过尺寸，靠边界圆柱裁出干净 2.5 孔）
D_BOSS, D_POST = -6.0, -13.0    # 凸台/柱底相对计划面的法向深度
BURR_R = 3.0                    # 球磨半径（面/台）
OVER_BAND = 0.30                # 过磨统计带（计划面下方 0.3mm 内）
ANN_EXCL = 0.6                  # 统计口径排除的台/柱/板壁过渡环带宽

BONE_COLOR = np.array([0.86, 0.78, 0.66])


# ---------------- 计划面坐标系 ----------------
def plan_T():
    """计划面位姿：旋转（倾角+后倾角）+ 平移到中心；返回 4x4 与法向 n"""
    R = (trimesh.transformations.rotation_matrix(np.radians(TILT_I), [1, 0, 0])
         @ trimesh.transformations.rotation_matrix(np.radians(TILT_V), [0, 1, 0]))
    T = R.copy()
    T[:3, 3] = [0.0, 0.0, C_Z]
    n = R[:3, :3] @ np.array([0.0, 0.0, 1.0])
    return T, n


T_PLAN, N_PLAN = plan_T()


def to_world(p_plan):
    """计划面坐标 [x, y, s] -> 世界坐标"""
    return (T_PLAN[:3, :3] @ np.asarray(p_plan, float)) + T_PLAN[:3, 3]


def to_plan(p_world):
    """世界坐标 -> 计划面坐标 (x, y, s)，支持 (N,3) 批量"""
    q = np.atleast_2d(np.asarray(p_world, float)) - T_PLAN[:3, 3]
    return q @ T_PLAN[:3, :3]          # 行向量乘 R 等价于 R^T·q


def D_of_r(r):
    """半径 r 处的计划面法向深度（计划地板）"""
    return np.where(r < R_POST, D_POST,
                    np.where(r < R_BOSS, D_BOSS, 0.0))


# ---------------- 场景与计划实体构建 ----------------
def make_glenoid():
    """骨块（顶面刻凹形盂窝 + 低频噪声），水密实体"""
    box = trimesh.creation.box(extents=[44, 44, Z_TOP])
    box.apply_translation([0, 0, Z_TOP / 2])
    cup = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    S = np.eye(4); S[0, 0], S[1, 1], S[2, 2] = CUP_A, CUP_B, CUP_C
    cup.apply_transform(S)
    cup.apply_translation([0, 0, Z_TOP + CUP_LIFT])
    bone = trimesh.boolean.difference([box, cup], engine="manifold")
    # 低频确定性表面噪声（幅度 0.05mm，保持水密）
    v = bone.vertices.copy()
    nz = (0.05 * np.sin(0.7 * v[:, 0] + 1.3) * np.sin(0.8 * v[:, 1] + 0.5)
          + 0.04 * np.sin(0.25 * v[:, 0]) * np.sin(0.3 * v[:, 1]))
    top = v[:, 2] > Z_TOP - 3.0
    v[top, 2] += nz[top]
    return trimesh.Trimesh(v, bone.faces, process=False)


def _cyl_plan(radius, s0, s1, sections=64):
    """计划坐标系中的圆柱（沿 s 轴，s0~s1）"""
    m = trimesh.creation.cylinder(radius=radius, sections=sections,
                                  segment=[[0, 0, s0], [0, 0, s1]])
    return m


def _box_plan(x0, x1, y0, y1, s0, s1):
    """计划坐标系中的长方体"""
    m = trimesh.creation.box(extents=[x1 - x0, y1 - y0, s1 - s0])
    m.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (s0 + s1) / 2])
    return m


def to_world_mesh(m):
    """把计划坐标系网格变换到世界"""
    w = m.copy()
    w.apply_transform(T_PLAN)
    return w


def plan_solids():
    """计划圆柱（全域）、目标保留实体（各地板以下）、各相位触觉边界圆柱"""
    cyl_all = to_world_mesh(_cyl_plan(R_PLATE, -20, 20))
    target = to_world_mesh(_cyl_plan(R_PLATE, -20, 0))            # 平面以下
    boss_band = to_world_mesh(_cyl_plan(R_BOSS, D_BOSS, 0))       # 凸台腔（待去除）
    post_band = to_world_mesh(_cyl_plan(R_POST, D_POST, D_BOSS))  # 柱腔（待去除）
    target = trimesh.boolean.difference([target, boss_band, post_band],
                                        engine="manifold")
    # 触觉边界（AccuStop 建模）：各相位工具只在对应边界内有效
    # 边界圆柱用 128 边（内接圆误差 <0.003mm），避免与工具多边形离散产生残环
    bounds = {"面粗": to_world_mesh(_cyl_plan(R_PLATE, -20, 20, sections=128)),
              "面精": to_world_mesh(_cyl_plan(R_PLATE, -20, 20, sections=128)),
              "台粗": to_world_mesh(_cyl_plan(R_BOSS, -20, 20, sections=128)),
              "台精": to_world_mesh(_cyl_plan(R_BOSS, -20, 20, sections=128)),
              "柱钻": to_world_mesh(_cyl_plan(R_POST, -20, 20, sections=128))}
    return cyl_all, target, bounds


def overcut_band_solid():
    """过磨统计带实体：各地板下方 0.3mm 的薄层（体积口径过磨计算用）"""
    b1 = to_world_mesh(_cyl_plan(R_PLATE, -OVER_BAND, 0))
    b2 = to_world_mesh(_cyl_plan(R_BOSS, D_BOSS - OVER_BAND, D_BOSS))
    b3 = to_world_mesh(_cyl_plan(R_POST, D_POST - OVER_BAND, D_POST))
    return trimesh.boolean.union([b1, b2, b3], engine="manifold")


def should_remove_volume(bone, cyl_all, target):
    """应去除体积 = 圆柱内体积 − 圆柱内且在各地板以下的体积"""
    v_in = trimesh.boolean.intersection([bone, cyl_all], engine="manifold").volume
    v_keep = trimesh.boolean.intersection([bone, target], engine="manifold").volume
    return v_in - v_keep


# ---------------- 磨削轨迹（计划坐标） ----------------
def _rows(radius, row_step, seg_step):
    """计划坐标系井字路径段（弓形），返回 [(p0_plan, p1_plan)]
    用 linspace 保证首末行贴边（arange 会在边缘留缺口）"""
    segs = []
    n_rows = int(np.ceil(2 * radius / row_step)) + 1
    ys = np.linspace(-radius, radius, n_rows)
    for i, y in enumerate(ys):
        half = np.sqrt(max(radius ** 2 - y ** 2, 1e-6))
        x0, x1 = -half, half
        if i % 2 == 1:
            x0, x1 = x1, x0
        L = abs(x1 - x0)
        n_seg = max(int(L / seg_step), 1)
        xs = np.linspace(x0, x1, n_seg + 1)
        for j in range(n_seg):
            segs.append(((xs[j], y, 0.0), (xs[j + 1], y, 0.0)))
    return segs


def sweep_capsule(r_tool, p0, p1):
    """世界坐标胶囊（球沿线段的精确扫掠）"""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    L = float(np.linalg.norm(d))
    if L < 1e-9:
        s = trimesh.creation.icosphere(subdivisions=3, radius=r_tool)
        s.apply_translation(p0)
        return s
    cap = trimesh.creation.capsule(radius=r_tool, height=L, count=(8, 16))
    cap.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], d))
    cap.apply_translation((p0 + p1) / 2)
    return cap


def trajectory():
    """五相位轨迹：[(相位名, 工具半径, (p0_plan), (p1_plan))]
    行中心半径 ≈ 计划半径 −（扫掠球在地板高度的横向触及半径），
    以保证腔壁达到计划半径（凸台 r=5.5 → 行半径 5.5−1.0=4.5 等）"""
    traj = []
    for name, s_c, rad in [("面粗", BURR_R + 0.7, R_PLATE - 0.8),
                           ("面精", BURR_R - 0.05, R_PLATE - 0.8)]:
        for p0, p1 in _rows(rad, 2.4, 4.0):
            traj.append((name, BURR_R, (p0[0], p0[1], s_c), (p1[0], p1[1], s_c)))
    for name, s_c in [("台粗", D_BOSS + BURR_R + 0.6),
                      ("台精", D_BOSS + BURR_R - 0.05)]:
        for p0, p1 in _rows(R_BOSS - 1.0, 2.0, 3.0):
            traj.append((name, BURR_R, (p0[0], p0[1], s_c), (p1[0], p1[1], s_c)))
    # 柱钻：中心竖直渐进（每步一小段）
    ss = np.arange(0.5, D_POST + POST_TOOL_R - 0.05 - 1e-9, -1.5)
    ss = np.append(ss, D_POST + POST_TOOL_R - 0.05)
    for k in range(len(ss) - 1):
        traj.append(("柱钻", POST_TOOL_R, (0, 0, ss[k]), (0, 0, ss[k + 1])))
    return traj


# ---------------- 状态着色与统计 ----------------
ORIG_MIN_S = None   # 初始骨面在计划圆柱内的最小 s
ORIG_GRID = None    # 初始表面高度栅格（计划 XY，用于过磨过滤）
ORIG_LIM = 14.0     # 栅格半宽


def build_orig_grid(bone, n=240):
    """初始表面高度栅格：每个格取初始顶点的最大 s（近似初始表面高度）"""
    global ORIG_GRID
    P = to_plan(bone.vertices)
    r = np.hypot(P[:, 0], P[:, 1])
    sel = r < ORIG_LIM
    xs, ys, ss = P[sel, 0], P[sel, 1], P[sel, 2]
    ix = np.clip(((xs + ORIG_LIM) / (2 * ORIG_LIM) * n).astype(int), 0, n - 1)
    iy = np.clip(((ys + ORIG_LIM) / (2 * ORIG_LIM) * n).astype(int), 0, n - 1)
    grid = np.full((n, n), -1e9)
    np.maximum.at(grid, (iy, ix), ss)
    ORIG_GRID = grid


def _orig_s(xy):
    """查初始表面高度（无数据返回 +inf 表示未知，视为不过滤）"""
    n = ORIG_GRID.shape[0]
    x, y = np.atleast_1d(xy[:, 0]), np.atleast_1d(xy[:, 1])
    ix = np.clip(((x + ORIG_LIM) / (2 * ORIG_LIM) * n).astype(int), 0, n - 1)
    iy = np.clip(((y + ORIG_LIM) / (2 * ORIG_LIM) * n).astype(int), 0, n - 1)
    v = ORIG_GRID[iy, ix]
    return np.where(v < -1e8, np.inf, v)


def face_state(mesh):
    """面分类（材料侧感知 + 统计口径修正）：
    剩余（显示）= 材料侧探针仍在去除区；过磨（显示）= 质心低于地板且在带内
    统计口径（返回 rem_stat/over_stat）额外排除：
      ① 台/柱/板壁过渡环带（|r-R|<0.6，两相位边界处的薄檐与离散残环）
      ② 过磨须初始面高于当地地板（排除天然低于计划面的区域）"""
    tri = mesh.vertices[mesh.faces]
    cen = tri.mean(axis=1)
    nrm = mesh.face_normals
    # --- 剩余判定：材料侧探针 ---
    probe = cen - 0.08 * nrm
    Pp = to_plan(probe)
    rp = np.hypot(Pp[:, 0], Pp[:, 1])
    sp = Pp[:, 2]
    d_rem = sp - D_of_r(rp)
    rem = (rp < R_PLATE) & (d_rem > 0.01)
    # --- 过磨判定：质心 + 统计带 ---
    Pc = to_plan(cen)
    rc = np.hypot(Pc[:, 0], Pc[:, 1])
    sc = Pc[:, 2]
    d_c = sc - D_of_r(rc)
    lower = np.maximum(D_of_r(rc) - OVER_BAND, ORIG_MIN_S + 0.02)
    over = (rc < R_PLATE) & (d_c < -0.005) & (sc > lower)
    # --- 统计口径：排除过渡环带；实心柱判定（d<1mm，排除悬空薄层）---
    ann = ((np.abs(rc - R_PLATE) < ANN_EXCL) | (np.abs(rc - R_BOSS) < ANN_EXCL)
           | (np.abs(rc - R_POST) < ANN_EXCL))
    rem_stat = rem & ~ann & (d_rem < 1.0)
    # 悬空薄层：远离当地地板的剩余面（相位间遗留薄壳，记为退化情形）
    thin_sheet = rem & ~ann & (d_rem >= 1.0)
    orig_s = _orig_s(Pc[:, :2])
    over_stat = over & ~ann & (orig_s > D_of_r(rc) + 0.05)

    light = np.array([0.35, 0.25, 0.90]); light /= np.linalg.norm(light)
    shade = 0.45 + 0.55 * np.clip(nrm @ light, 0, 1)
    colors = np.tile(BONE_COLOR, (len(cen), 1))
    if rem.any():
        t = np.clip(d_rem[rem] / 2.2, 0, 1)      # 剩余深度归一（最深 ~2.2mm）
        colors[rem] = plt.cm.Blues(0.35 + 0.55 * t)[:, :3]
    if over.any():
        t = np.clip(-d_c[over] / OVER_BAND, 0, 1)
        colors[over] = np.stack([np.ones_like(t), 0.85 - 0.85 * t,
                                 0.25 - 0.25 * t], axis=1)
    return (np.clip(colors * shade[:, None], 0, 1), d_rem, rem, over, d_c,
            rem_stat, over_stat, thin_sheet)


def affected_count(mesh, p0w, p1w, r_tool, margin=1.0):
    tri = mesh.vertices[mesh.faces]
    cen = tri.mean(axis=1)
    a, b = np.asarray(p0w), np.asarray(p1w)
    ab = b - a
    L2 = float(ab @ ab)
    t = np.clip(((cen - a) @ ab) / (L2 + 1e-12), 0, 1)[:, None]
    dd = np.linalg.norm(cen - (a + t * ab), axis=1)
    return int((dd < r_tool + margin).sum())


# ---------------- 渲染 ----------------
def render_frame(mesh, tool_c, tool_r, title, path, dpi=72):
    fig = plt.figure(figsize=(6.6, 5.0))
    ax = fig.add_subplot(111, projection="3d")
    pc = Poly3DCollection(mesh.vertices[mesh.faces],
                          facecolors=face_state(mesh)[0], edgecolor="none")
    ax.add_collection3d(pc)
    # 计划面圆盘（倾斜）
    th = np.linspace(0, 2 * np.pi, 48)
    ring = np.array([to_world([R_PLATE * c, R_PLATE * sn, 0.0])
                     for c, sn in zip(np.cos(th), np.sin(th))])
    c0 = to_world([0, 0, 0])
    disk = [np.array([c0, ring[k], ring[k + 1]]) for k in range(47)]
    ax.add_collection3d(Poly3DCollection(disk, facecolors=(0.2, 0.2, 0.2, 0.13),
                                         edgecolor="none"))
    if tool_c is not None:
        burr = trimesh.creation.icosphere(subdivisions=2, radius=tool_r)
        bt = np.asarray(burr.triangles) + np.asarray(tool_c) - burr.vertices.mean(0)
        ax.add_collection3d(Poly3DCollection(bt, facecolors=(0.9, 0.15, 0.1, 0.30),
                                             edgecolor="none"))
    ax.set_xlim(-22, 22); ax.set_ylim(-22, 22); ax.set_zlim(0, 14)
    ax.set_box_aspect((44, 44, 14))
    ax.view_init(elev=28, azim=-60)
    ax.set_title(title, fontsize=8)
    ax.set_axis_off()
    fig.tight_layout(pad=0.2)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


# ---------------- 主流程 ----------------
def main():
    global ORIG_MIN_S
    print("[1/5] 构建场景（凹形盂窝 + 倾斜非平面计划面）...")
    bone = make_glenoid()
    bone0 = bone.copy()          # 初始骨面副本（过磨体积对拍用）
    v0 = bone.volume
    cyl_all, target, bounds = plan_solids()
    should = should_remove_volume(bone, cyl_all, target)
    # 初始骨面在计划圆柱内的最小法向坐标（用于过磨带下界）
    P = to_plan(bone.vertices)
    rr = np.hypot(P[:, 0], P[:, 1])
    ORIG_MIN_S = float(P[rr < R_PLATE, 2].min())
    build_orig_grid(bone)
    print(f"      初始体积 {v0:.1f} mm³ | 计划应去除 {should:.1f} mm³ | "
          f"初始面数 {len(bone.faces)} | 初始面最低 s={ORIG_MIN_S:.2f} mm")
    assert bone.is_watertight

    traj = trajectory()
    print(f"[2/5] 五相位磨削轨迹共 {len(traj)} 步")

    print("[3/5] 增量更新循环 ...")
    frames, rows = [], []
    t_bools = []
    fid = 0
    first_tool = to_world(traj[0][2])
    render_frame(bone, first_tool, traj[0][1], "初始凹形盂窝 | 灰盘=倾斜计划面",
                 os.path.join(FRAMES, "f0000.png"))
    frames.append("f0000.png")
    fid = 1
    fail_events = []
    for k, (name, r_tool, p0p, p1p) in enumerate(traj):
        w0, w1 = to_world(p0p), to_world(p1p)
        # 触觉边界建模：工具先裁剪到当前相位的计划边界内（AccuStop 语义）
        tool = trimesh.boolean.intersection(
            [sweep_capsule(r_tool, w0, w1), bounds[name]], engine="manifold")
        t0 = time.perf_counter()
        try:
            bone = trimesh.boolean.difference([bone, tool], engine="manifold")
        except Exception as e:
            fail_events.append((name, k + 1, str(e)))
            continue
        t_bool = (time.perf_counter() - t0) * 1000
        t_bools.append(t_bool)
        if not bone.is_watertight:
            fail_events.append((name, k + 1, "非水密"))
        removed = v0 - bone.volume
        pct = removed / should * 100
        na = affected_count(bone, w0, w1, r_tool)
        render_frame(bone, (w0 + w1) / 2, r_tool,
                     f"{name} {k+1}/{len(traj)} | 去除 {removed:.0f}mm³({pct:.0f}%) "
                     f"| 更新 {t_bool:.0f}ms | 受影响 {na}/{len(bone.faces)}",
                     os.path.join(FRAMES, f"f{fid:04d}.png"))
        frames.append(f"f{fid:04d}.png")
        rows.append([name, k + 1, round(t_bool, 1), len(bone.faces), na,
                     round(removed, 1)])
        fid += 1
        if (k + 1) % 20 == 0:
            print(f"      {k+1}/{len(traj)} 面数 {len(bone.faces)} {t_bool:.0f}ms")

    print("[4/5] 统计与动画 ...")
    _, d_rem, rem, over, d_c, rem_stat, over_stat, thin = face_state(bone)
    rem_max = float(d_rem[rem_stat].max()) if rem_stat.any() else 0.0
    over_min = float(d_c[over_stat].min()) if over_stat.any() else 0.0
    n_sheet = int(thin.sum())
    removed = v0 - bone.volume
    # 过磨体积（布尔对拍口径）：统计带内 初始−最终 的体积差
    band = overcut_band_solid()
    overcut_vol = (trimesh.boolean.intersection([bone0, band], engine="manifold").volume
                   - trimesh.boolean.intersection([bone, band], engine="manifold").volume)

    imgs = [Image.open(os.path.join(FRAMES, f)) for f in frames]
    imgs[0].save(os.path.join(OUT, "E1磨削全流程.gif"),
                 save_all=True, append_images=imgs[1:], duration=GIF_MS, loop=0)
    picks = [frames[i] for i in (0, len(frames) // 5, 2 * len(frames) // 5,
                                 3 * len(frames) // 5, 4 * len(frames) // 5,
                                 len(frames) - 1)]
    fig, axes = plt.subplots(1, 6, figsize=(22, 3.8))
    for ax, f in zip(axes, picks):
        ax.imshow(Image.open(os.path.join(FRAMES, f))); ax.axis("off")
    fig.suptitle("E1 关键帧：凹形盂窝 → 面粗/面精 → 凸台 → 中央柱（蓝=剩余 黄红=过磨）",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "E1关键帧拼图.png"), dpi=100)
    plt.close(fig)

    with open(os.path.join(OUT, "e1_timing.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["phase", "step", "t_bool_ms", "faces", "affected", "removed_mm3"])
        w.writerows(rows)

    print("[5/5] 摘要")
    tb = np.array(t_bools)
    summary = (
        f"计划应去除: {should:.1f} mm3\n"
        f"实际去除: {removed:.1f} mm3 (完成度 {removed/should*100:.1f}%)\n"
        f"剩余脊高(法向,实心柱口径): {rem_max:.3f} mm\n"
        f"过磨体积(0.3mm统计带,体积口径): {overcut_vol:.2f} mm3 "
        f"(面口径最大深度 {over_min:.3f} mm)\n"
        f"悬空薄层面数(相位间遗留,退化情形): {n_sheet}\n"
        f"布尔步数: {len(t_bools)} | 平均 {tb.mean():.1f} ms / 最大 {tb.max():.1f} ms"
        f" -> 纯更新等效 {1000/tb.mean():.0f} fps\n"
        f"最终面数: {len(bone.faces)} (初始 {len(make_glenoid().faces)}) | "
        f"水密: {bone.is_watertight}\n"
        f"退化事件: {len(fail_events)}" +
        (f" -> {fail_events[:5]}" if fail_events else "（布尔/水密层面无）")
    )
    print(summary)
    with open(os.path.join(OUT, "e1_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary + "\n")
    print("完成。输出：", OUT)


if __name__ == "__main__":
    main()
