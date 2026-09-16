"""只读核对两个指定整骨输入，记录质量基线及float转换损失。"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import trimesh


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    results = []
    for name in ("initial.obj", "raw_2.obj"):
        source = ROOT / "初步实验/CUDA真实骨面对照/强基线覆盖结果/20260908_132411" / name
        mesh = trimesh.load(source, force="mesh", process=False)
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces)
        tri = vertices[faces]
        edges = np.stack((tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 1], tri[:, 0] - tri[:, 2]), axis=1)
        lengths = np.linalg.norm(edges, axis=2)
        area2 = np.linalg.norm(np.cross(edges[:, 0], -edges[:, 2]), axis=1)
        quality = 2 * np.sqrt(3) * area2 / np.sum(lengths ** 2, axis=1)
        angles = []
        for i in range(3):
            j, k = (i + 1) % 3, (i + 2) % 3
            cosine = (lengths[:, j] ** 2 + lengths[:, k] ** 2 - lengths[:, i] ** 2) / (2 * lengths[:, j] * lengths[:, k])
            angles.append(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
        minimum_angles = np.min(angles, axis=0)
        conversion = np.linalg.norm(vertices.astype(np.float32).astype(np.float64) - vertices, axis=1)
        results.append({
            "input": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "vertices": len(vertices), "faces": len(faces), "bounds_mm": mesh.bounds.tolist(),
            "watertight_edge_test": bool(mesh.is_watertight), "winding_consistent": bool(mesh.is_winding_consistent),
            "euler_number": int(mesh.euler_number), "q_min": float(quality.min()),
            "angle_min_deg": float(minimum_angles.min()), "q_below_0_4_faces": int(np.sum(quality < 0.4)),
            "angle_below_25_faces": int(np.sum(minimum_angles < 25)), "zero_area_faces": int(np.sum(area2 == 0)),
            "float_conversion_max_mm": float(conversion.max()), "gpu_remesh_executed": False,
            "scope": "全输入面；水密边计数不等于无自交；未执行自交及几何距离证书检查",
        })
    output = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
              "units": "mm，沿用输入实验坐标，未归一化", "results": results}
    (HERE / "输入核对.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
