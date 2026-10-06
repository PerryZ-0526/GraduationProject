"""生成可重复的几何体和磨削运动，按几何体划分开发与保留评价输入。"""

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_body(family, variant):
    """尺度单位为毫米；同一家族改变形状与特征尺度，不仅改变轨迹。"""
    scale = 1 + 0.07 * variant
    if family == "板体":
        mesh = trimesh.creation.box(extents=[12 * scale, 10, 3 + variant * 0.2])
    elif family in ("球体", "椭球", "弯曲骨样体"):
        mesh = trimesh.creation.icosphere(subdivisions=3, radius=5 * scale)
        if family == "椭球":
            mesh.vertices *= [1.6, 0.8, 0.55 + 0.03 * variant]
        elif family == "弯曲骨样体":
            mesh.vertices *= [0.65, 0.8, 1.8]
            mesh.vertices[:, 0] += 0.04 * mesh.vertices[:, 2] ** 2
    elif family == "贯通孔":
        mesh = trimesh.creation.annulus(r_min=0.15 + 0.12 * variant, r_max=5 * scale, height=2, sections=64)
    elif family == "薄壁":
        mesh = trimesh.creation.box(extents=[12, 10, 0.03 * 2 ** variant])
    elif family == "窄缝":
        gap = 0.03 * 2 ** variant
        pieces = []
        for sign in (-1, 1):
            part = trimesh.creation.box(extents=[5, 10, 3])
            part.apply_translation([sign * (2.5 + gap / 2), 0, 0])
            pieces.append(part)
        mesh = trimesh.util.concatenate(pieces)
    else:
        raise ValueError(family)
    return mesh


def routes(mesh):
    """冻结四种运动：浅磨、交叉、重复与32段长路线；全部为仿真切削。"""
    low, high = mesh.bounds
    radius = min(0.6, float(np.min(mesh.extents)) * 0.4)
    height = high[2] + radius * 0.35
    x, y = mesh.extents[:2] * 0.3
    shallow = np.column_stack([np.linspace(-x, x, 9), np.zeros(9), np.full(9, height)])
    cross = np.array([[-x, -y, height], [x, y, height], [-x, y, height], [x, -y, height]])
    repeat = np.vstack([shallow, shallow[-2::-1], shallow[1:]])
    t = np.linspace(0, 4 * np.pi, 33)
    long = np.column_stack([x * np.cos(t), y * np.sin(t), height - radius * 0.15 * t / t[-1]])
    return [(name, points, radius) for name, points in zip(("浅磨", "交叉", "重复", "长序列"), (shallow, cross, repeat, long))]


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": 1, "time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "units": {"length": "mm", "time": "ms"}, "source": "确定性程序生成，无患者数据",
                "split_rule": "每家族变体0、1用于开发，2、3、4用于保留评价；同体全部路线同一划分",
                "reference": "输入多边形几何；没有连续CSG真值或距离证书", "bodies": []}
    for family in ("板体", "球体", "椭球", "弯曲骨样体", "贯通孔", "薄壁", "窄缝"):
        for variant in range(5):
            mesh = make_body(family, variant)
            body_id = f"{family}_{variant:02d}"
            path = output / (body_id + ".obj")
            # 保存17位有效数字，避免OBJ默认精度使窄特征提前消失。
            with path.open("w", encoding="utf-8") as stream:
                for vertex in mesh.vertices:
                    stream.write("v " + " ".join(format(float(v), ".17g") for v in vertex) + "\n")
                for face in mesh.faces:
                    stream.write("f " + " ".join(str(int(v) + 1) for v in face) + "\n")
            item = {"id": body_id, "family": family, "variant": variant,
                    "split": "development" if variant < 2 else "held_out",
                    "mesh": path.name, "sha256": digest(path), "bounds": mesh.bounds.tolist(),
                    "faces": len(mesh.faces), "components": len(mesh.split(only_watertight=False)),
                    "watertight": bool(mesh.is_watertight), "winding_consistent": bool(mesh.is_winding_consistent),
                    "routes": []}
            for name, points, radius in routes(mesh):
                route_path = output / f"{body_id}_{name}.json"
                motion = {"body_id": body_id, "tool_radius_mm": radius, "simulation": True,
                          "events": [{"index": i, "time_ms": 100 * i, "position_mm": p.tolist(), "cutting": True}
                                     for i, p in enumerate(points)]}
                route_path.write_text(json.dumps(motion, ensure_ascii=False, indent=2), encoding="utf-8")
                item["routes"].append({"name": name, "file": route_path.name, "sha256": digest(route_path), "segments": len(points) - 1})
            manifest["bodies"].append(item)
    manifest["generator_sha256"] = digest(Path(__file__))
    (output / "01-测试集清单.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(args.output)
    print(json.dumps({"bodies": len(result["bodies"]), "routes": sum(len(b["routes"]) for b in result["bodies"])}, ensure_ascii=False))
