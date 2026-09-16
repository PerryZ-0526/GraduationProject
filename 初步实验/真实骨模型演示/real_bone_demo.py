# -*- coding: utf-8 -*-
"""
真实骨模型增量磨削演示（视觉升级版）
====================================
在真实 CT 重建的肩胛骨（Zenodo 14590062，犹他大学 Henninger 实验室，
hill_sachs_001_F_37_R 标本，40,086 面水密网格）上运行磨削管线：
  计划面自动定位：盂中心用数据集 CSV 的解剖标志点（GC），法向由盂面
  9mm 邻域平面拟合得到（起伏仅 ±0.6mm，即盂窝面本身）。
渲染升级（相对 E1/课题规划与专题调研目录的 13 号报告）：
  1. 不为磨钻建模——当前磨削区域以高亮色直接标在骨面上（移动亮带）；
  2. 双光源 + Blinn-Phong 高光，深色背景，立体感增强；
  3. 整个肩胛骨可见（真实解剖形态自带立体线索）。
状态色：蓝=剩余待去除，黄红=过磨，亮橙=当前正在磨削区域，米色=未磨骨面。
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
FRAMES_C = os.path.join(OUT, "frames_close")
os.makedirs(FRAMES, exist_ok=True)
os.makedirs(FRAMES_C, exist_ok=True)
GIF_MS = 100

# ---------------- 模型与计划参数 ----------------
SCAP_STL = os.path.join(OUT, "scapula_hill_sachs_001_R.stl")
GC = np.array([-119.5, -104.9, -94.1])   # 数据集标志点：盂中心（glenoid center）
FIT_R = 9.0                               # 盂面法向拟合邻域半径

R_PLATE, R_BOSS, R_POST = 12.5, 5.5, 2.5  # 基板/凸台/柱半径（Perform 规格）
D_BOSS, D_POST = -4.5, -8.0               # 凸台/柱深度（按该标本盂窝厚度调低）
BURR_R = 3.0
POST_TOOL_R = 2.9                          # 过尺寸，由边界圆柱裁出干净 2.5 孔
OVER_BAND = 0.30
ANN_EXCL = 0.6

BONE_COLOR = np.array([0.88, 0.80, 0.68])
ACTIVE_COLOR = np.array([1.00, 0.45, 0.10])  # 当前磨削区高亮


# ---------------- 计划面坐标系 ----------------
def fit_glenoid_frame(mesh):
    """用盂中心标志点 + 盂面拟合平面，构造计划面位姿（4x4）与法向"""
    v = mesh.vertices
    d = np.linalg.norm(v - GC, axis=1)
    patch = v[d < FIT_R]
    c0 = patch.mean(0)
    _, _, vt = np.linalg.svd(patch - c0)
    n = vt[-1]
    if n @ (GC - mesh.centroid) < 0:      # 法向朝外
        n = -n
    R = trimesh.geometry.align_vectors([0, 0, 1], n)
    T = R.copy()
    T[:3, 3] = GC
    return T, n


T_PLAN, N_PLAN = None, None               # main 中初始化（依赖网格）


def to_world(p_plan):
    return (T_PLAN[:3, :3] @ np.asarray(p_plan, float)) + T_PLAN[:3, 3]


def to_plan(p_world):
    q = np.atleast_2d(np.asarray(p_world, float)) - T_PLAN[:3, 3]
    return q @ T_PLAN[:3, :3]


def D_of_r(r):
    return np.where(r < R_POST, D_POST,
                    np.where(r < R_BOSS, D_BOSS, 0.0))


# ---------------- 计划实体 / 轨迹 ----------------
def _cyl_plan(radius, s0, s1, sections=128):
    return trimesh.creation.cylinder(radius=radius, sections=sections,
                                     segment=[[0, 0, s0], [0, 0, s1]])


def to_world_mesh(m):
    w = m.copy()
    w.apply_transform(T_PLAN)
    return w


def plan_solids():
    cyl_all = to_world_mesh(_cyl_plan(R_PLATE, -20, 20))
    target = to_world_mesh(_cyl_plan(R_PLATE, -20, 0))
    boss_band = to_world_mesh(_cyl_plan(R_BOSS, D_BOSS, 0))
    post_band = to_world_mesh(_cyl_plan(R_POST, D_POST, D_BOSS))
    target = trimesh.boolean.difference([target, boss_band, post_band],
                                        engine="manifold")
    bounds = {n: to_world_mesh(_cyl_plan(r, -20, 20))
              for n, r in [("面粗", R_PLATE), ("面精", R_PLATE),
                           ("台粗", R_BOSS), ("台精", R_BOSS),
                           ("柱钻", R_POST)]}
    return cyl_all, target, bounds


def _rows(radius, row_step, seg_step):
    segs = []
    n_rows = int(np.ceil(2 * radius / row_step)) + 1
    ys = np.linspace(-radius, radius, n_rows)
    for i, y in enumerate(ys):
        half = np.sqrt(max(radius ** 2 - y ** 2, 1e-6))
        x0, x1 = -half, half
        if i % 2 == 1:
            x0, x1 = x1, x0
        n_seg = max(int(abs(x1 - x0) / seg_step), 1)
        xs = np.linspace(x0, x1, n_seg + 1)
        for j in range(n_seg):
            segs.append(((xs[j], y, 0.0), (xs[j + 1], y, 0.0)))
    return segs


def sweep_capsule(r_tool, p0, p1):
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
    traj = []
    for name, s_c in [("面粗", BURR_R + 0.7), ("面精", BURR_R - 0.05)]:
        for p0, p1 in _rows(R_PLATE - 0.8, 1.5, 5.0):   # 行距≈球半径一半：交叠覆盖，消除条纹刻痕:
            traj.append((name, BURR_R, (p0[0], p0[1], s_c), (p1[0], p1[1], s_c)))
    for name, s_c in [("台粗", D_BOSS + BURR_R + 0.6),
                      ("台精", D_BOSS + BURR_R - 0.05)]:
        for p0, p1 in _rows(R_BOSS - 1.0, 1.5, 3.0):   # 行距≈球半径一半（同面相位）:
            traj.append((name, BURR_R, (p0[0], p0[1], s_c), (p1[0], p1[1], s_c)))
    ss = np.arange(0.5, D_POST + POST_TOOL_R - 0.05 - 1e-9, -1.5)
    ss = np.append(ss, D_POST + POST_TOOL_R - 0.05)
    for k in range(len(ss) - 1):
        traj.append(("柱钻", POST_TOOL_R, (0, 0, ss[k]), (0, 0, ss[k + 1])))
    return traj


# ---------------- 着色（含当前磨削高亮） ----------------
def face_colors(mesh, tool_seg=None, tool_r=0.0):
    """返回着色：状态色（蓝/黄红/米色）+ 当前磨削区高亮（亮橙）"""
    tri = mesh.vertices[mesh.faces]
    cen = tri.mean(axis=1)
    nrm = mesh.face_normals
    # 状态分类（材料侧感知，同 E1）
    probe = cen - 0.08 * nrm
    Pp = to_plan(probe)
    rp = np.hypot(Pp[:, 0], Pp[:, 1])
    d_rem = Pp[:, 2] - D_of_r(rp)
    rem = (rp < R_PLATE) & (d_rem > 0.01)
    Pc = to_plan(cen)
    rc = np.hypot(Pc[:, 0], Pc[:, 1])
    d_c = Pc[:, 2] - D_of_r(rc)
    over = (rc < R_PLATE) & (d_c < -0.005) & (Pc[:, 2] > D_of_r(rc) - OVER_BAND)

    colors = np.tile(BONE_COLOR, (len(cen), 1))
    if rem.any():
        t = np.clip(d_rem[rem] / 1.5, 0, 1)
        # 剩余深度分级色：深剩余=饱和蓝，浅剩余(<0.3mm)=淡蓝向骨色渐隐（平滑高度场观感）
        shallow = t < 0.25
        deep = ~shallow
        cols = np.stack([0.25 + 0.45 * t, 0.52 + 0.30 * t, 0.98 - 0.10 * t], axis=1)
        # 浅剩余：向骨色插值（插值系数随深度 0->0.25 从 0.75->0.1）
        a = 0.10 + (t / 0.25) * 0.65
        cols = a[:, None] * cols + (1 - a)[:, None] * BONE_COLOR
        colors[rem] = cols
    if over.any():
        t = np.clip(-d_c[over] / OVER_BAND, 0, 1)
        colors[over] = np.stack([np.ones_like(t), 0.80 - 0.55 * t,
                                 0.20 - 0.12 * t], axis=1)
    # 当前磨削区高亮：距当前扫掠轴 < 工具半径+1.2 的面
    act = np.zeros(len(cen), bool)
    if tool_seg is not None:
        a, b = np.asarray(tool_seg[0]), np.asarray(tool_seg[1])
        ab = b - a
        L2 = float(ab @ ab)
        t_ = np.clip(((cen - a) @ ab) / (L2 + 1e-12), 0, 1)[:, None]
        dd = np.linalg.norm(cen - (a + t_ * ab), axis=1)
        act = dd < tool_r + 1.2
    return colors, nrm, act


def shade_colors(colors, nrm, act=None):
    """双光源漫反射 + 相机补光 + 高光；高亮面保持醒目（不低于 0.85 亮度）"""
    L1 = np.array([0.45, 0.30, 0.84]); L1 /= np.linalg.norm(L1)
    L2 = np.array([-0.55, -0.25, 0.35]); L2 /= np.linalg.norm(L2)
    V = np.array([0.0, 0.0, 1.0])
    H = L1 + V; H /= np.linalg.norm(H)
    diff = (0.30 + 0.55 * np.clip(nrm @ L1, 0, 1)
            + 0.18 * np.clip(nrm @ L2, 0, 1)
            + 0.22 * np.clip(nrm @ V, 0, 1))
    spec = 0.22 * np.clip(nrm @ H, 0, 1) ** 24
    out = colors * diff[:, None] + spec[:, None] * np.array([1.0, 0.98, 0.92])
    if act is not None and act.any():
        out[act] = np.clip(out[act], 0.85, 1.0)
    return np.clip(out, 0, 1)


# ---------------- 渲染 ----------------
R_VIEW = None    # 世界->视图旋转（盂面法向对准 +Z），main 中初始化


def render_frame(mesh, tool_seg, tool_r, path, frac=0.0, dpi=92, closeup=False):
    fig = plt.figure(figsize=(7.2, 5.4))
    fig.patch.set_facecolor("#1c2229")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#1c2229")

    v = (mesh.vertices - GC) @ R_VIEW[:3, :3].T   # 视图旋转（行向量右乘 R.T ⇔ R·p）
    tri = v[mesh.faces]
    colors, nrm, act = face_colors(mesh, tool_seg, tool_r)
    shaded = shade_colors(colors, nrm, act)
    shaded[act] = ACTIVE_COLOR                     # 高亮面用纯亮橙（不被阴影压暗）
    pc = Poly3DCollection(tri, facecolors=shaded, edgecolor="none")
    ax.add_collection3d(pc)

    # 计划面圆环（青色细环标出计划边界）
    th = np.linspace(0, 2 * np.pi, 96)
    ring = np.array([to_world([R_PLATE * c, R_PLATE * s, 0.0])
                     for c, s in zip(np.cos(th), np.sin(th))])
    ring_v = (ring - GC) @ R_VIEW[:3, :3].T
    ax.plot(ring_v[:, 0], ring_v[:, 1], ring_v[:, 2],
            color="#39d0c8", lw=2.2, alpha=0.95)

    azim = -40 + 26 * np.sin(2 * np.pi * frac)     # ±26° 缓慢往返（视差->立体感）
    elev = 58 + 8 * np.cos(2 * np.pi * frac)       # 俯视盂面（蓝区可见），骨板下垂同框
    if closeup:
        # 特写：取景锁定盂面 ±42mm（磨削区充满画面）
        ext = np.array([42.0, 42.0, 42.0])
        ctr = np.zeros(3)                          # 已以 GC 为原点
        azim, elev = -30 + 14 * np.sin(2 * np.pi * frac), 62
    else:
        lo, hi = v.min(0), v.max(0)
        ctr = (lo + hi) / 2
        ext = (hi - lo) / 2 * 1.04 + 1e-6
    ax.set_xlim(ctr[0] - ext[0], ctr[0] + ext[0])
    ax.set_ylim(ctr[1] - ext[1], ctr[1] + ext[1])
    ax.set_zlim(ctr[2] - ext[2], ctr[2] + ext[2])
    ax.set_box_aspect((ext[0], ext[1], ext[2]))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(path, dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def postprocess(fp, canvas_wh):
    """裁掉空白边框：骨充满画面后居中贴到固定画布（各帧尺寸一致）"""
    from PIL import Image as Img
    im = Img.open(fp).convert("RGB")
    a = np.asarray(im, float) / 255
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    dark = (r < 0.25) & (g < 0.28) & (b < 0.33)
    ys, xs = np.nonzero(~dark)
    if len(xs) == 0:
        return im
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    m = 12  # 边距
    x0, y0 = max(x0 - m, 0), max(y0 - m, 0)
    x1, y1 = min(x1 + m, im.width - 1), min(y1 + m, im.height - 1)
    crop = im.crop((x0, y0, x1 + 1, y1 + 1))
    cw, ch = canvas_wh
    # 等比放大至画布（充满），再居中放置
    s = min(cw / crop.width, ch / crop.height)
    nw, nh = int(crop.width * s), int(crop.height * s)
    if s > 1:
        crop = crop.resize((nw, nh), Img.LANCZOS)
    canvas = Img.new("RGB", (cw, ch), "#1c2229")
    canvas.paste(crop, ((cw - nw) // 2, (ch - nh) // 2))
    return canvas


# ---------------- 主流程（可断点续跑：布尔态存 /tmp，渲染跳过已有帧） ----------------
STATE_DIR = "/tmp/rbd_states"          # VM 本地中间态（不占用户磁盘）
T_BUDGET = 135.0                       # 单次调用渲染时间预算（秒），超时优雅退出


def main():
    global T_PLAN, N_PLAN, R_VIEW
    os.makedirs(STATE_DIR, exist_ok=True)
    print("[1/5] 载入真实肩胛骨并定位计划面 ...")
    bone = trimesh.load(SCAP_STL)
    assert bone.is_watertight
    T_PLAN, N_PLAN = fit_glenoid_frame(bone)
    R_VIEW = trimesh.geometry.align_vectors(N_PLAN, [0, 0, 1])
    v0 = bone.volume
    cyl_all, target, bounds = plan_solids()
    should = (trimesh.boolean.intersection([bone, cyl_all], engine="manifold").volume
              - trimesh.boolean.intersection([bone, target], engine="manifold").volume)
    print(f"      面数 {len(bone.faces)} | 应去除 {should:.1f} mm³ | "
          f"盂面法向 {np.round(N_PLAN,2).tolist()}")

    traj = trajectory()
    print(f"[2/5] 轨迹 {len(traj)} 步（五相位）——布尔与中间态缓存")

    # ---- 阶段 A：布尔更新，存中间态（已有则跳过；计时存档复用）----
    t_bools = []
    tfile = os.path.join(STATE_DIR, "timing.npy")
    if os.path.exists(tfile):
        t_bools = list(np.load(tfile))
    meta = [("初始", None, 0.0, None)]
    np.savez_compressed(os.path.join(STATE_DIR, "s0000.npz"),
                        v=bone.vertices, f=bone.faces)
    for k, (name, r_tool, p0p, p1p) in enumerate(traj):
        sp = os.path.join(STATE_DIR, f"s{k+1:04d}.npz")
        w0, w1 = to_world(p0p), to_world(p1p)
        meta.append((name, w0, r_tool, w1))
        if os.path.exists(sp):
            continue
        tool = trimesh.boolean.intersection(
            [sweep_capsule(r_tool, w0, w1), bounds[name]], engine="manifold")
        t0 = time.perf_counter()
        bone = trimesh.boolean.difference([bone, tool], engine="manifold")
        t_bools.append((time.perf_counter() - t0) * 1000)
        np.savez_compressed(sp, v=bone.vertices, f=bone.faces)
        if (k + 1) % 20 == 0:
            print(f"      布尔 {k+1}/{len(traj)} 面数 {len(bone.faces)}")
    if t_bools:
        np.save(tfile, np.array(t_bools))
    final = None
    zf = np.load(os.path.join(STATE_DIR, f"s{len(traj):04d}.npz"))
    final = trimesh.Trimesh(zf["v"], zf["f"], process=False)
    print(f"      布尔态缓存完成（{len(os.listdir(STATE_DIR))} 个）")

    # ---- 阶段 B：逐帧渲染（全景 + 盂面特写；跳过已有帧，超时优雅退出）----
    print("[3/5] 渲染 ...")
    t_start = time.perf_counter()
    pending = []
    for i, (name, w0, r_tool, w1) in enumerate(meta):
        fp = os.path.join(FRAMES, f"f{i:04d}.png")
        fp_c = os.path.join(FRAMES_C, f"f{i:04d}.png")
        pending.append((i, fp, fp_c, name, w0, r_tool, w1))
    done = 0
    for i, fp, fp_c, name, w0, r_tool, w1 in pending:
        if os.path.exists(fp) and os.path.exists(fp_c):
            done += 1
            continue
        if time.perf_counter() - t_start > T_BUDGET:
            print(f"      时间预算用尽：已渲染 {done}/{len(pending)}，"
                  f"请再次运行以继续（断点续跑）")
            return
        z = np.load(os.path.join(STATE_DIR, f"s{i:04d}.npz"))
        m = trimesh.Trimesh(z["v"], z["f"], process=False)
        seg = (w0, w1) if w1 is not None else None
        frac = i / max(len(pending) - 1, 1)
        if not os.path.exists(fp):
            render_frame(m, seg, r_tool, fp, frac=frac)
        if not os.path.exists(fp_c):
            render_frame(m, seg, r_tool, fp_c, frac=frac, closeup=True)
        done += 1
    print(f"      渲染完成 {done}/{len(pending)}")

    print("[4/5] 后处理（裁剪充满画面）与合成 GIF ...")
    CW, CH = 760, 570          # 统一画布
    def build_gif(frames_dir, gif_name):
        fs = sorted(os.listdir(frames_dir))
        proc = [postprocess(os.path.join(frames_dir, f), (CW, CH)) for f in fs]
        proc[0].save(os.path.join(OUT, gif_name),
                     save_all=True, append_images=proc[1:], duration=GIF_MS, loop=0)
        return fs, proc
    frames, proc = build_gif(FRAMES, "真实肩胛骨磨削演示.gif")
    build_gif(FRAMES_C, "真实肩胛骨磨削演示_盂面特写.gif")
    picks = [proc[i] for i in (0, len(proc)//5, 2*len(proc)//5,
                               3*len(proc)//5, 4*len(proc)//5, len(proc)-1)]
    fig, axes = plt.subplots(1, 6, figsize=(22, 4.6), facecolor="#1c2229")
    for ax, im_ in zip(axes, picks):
        ax.imshow(im_)
        ax.axis("off")
    fig.suptitle("真实肩胛骨增量磨削：蓝=剩余 亮橙=当前磨削区 黄红=过磨 青环=计划边界",
                 fontsize=13, color="w")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "关键帧拼图.png"), dpi=100, facecolor="#1c2229")
    plt.close(fig)

    print("[5/5] 摘要")
    removed = v0 - final.volume
    tb = np.array(t_bools) if t_bools else np.array([0.0])
    summary = (
        f"模型: hill_sachs_001_F_37_R（真实 CT 重建，40,086 面，水密）\n"
        f"计划应去除: {should:.1f} mm3 | 实际去除: {removed:.1f} mm3 "
        f"(完成度 {removed/should*100:.1f}%)\n"
        f"布尔步数: {len(traj)} | 平均 {tb.mean():.0f} ms / 最大 {tb.max():.0f} ms"
        f" -> 纯更新等效 {1000/tb.mean():.0f} fps\n"
        f"最终面数: {len(final.faces)} | 水密: {final.is_watertight}\n"
        f"GIF 帧数: {len(frames)}"
    )
    print(summary)
    with open(os.path.join(OUT, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary + "\n")
    print("完成。输出：", OUT)


if __name__ == "__main__":
    main()
