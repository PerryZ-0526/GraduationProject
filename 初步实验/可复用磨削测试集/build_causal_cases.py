"""生成同几何、不同对角线的闭合输入，区分三角化质量与几何形状的影响。"""

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import trimesh


def write_mesh(mesh, path):
    """以17位有效数字保存；两种三角化均不移动输入多边形顶点。"""
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for vertex in mesh.vertices:
            stream.write("v " + " ".join(format(float(x), ".17g") for x in vertex) + "\n")
        for face in mesh.faces:
            stream.write("f " + " ".join(str(int(x) + 1) for x in face) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "units": {"length": "mm"}, "split": "development_diagnostic",
                "scope": "三个凸四边形柱体，两种表面对角线和两种相同球形工具；非独立评价或临床资产",
                "generator_sha256": digest(Path(__file__)), "pairs": []}
    quads = [[[0, 0], [2, 0], [2, 1], [.1, .6]],
             [[0, 0], [2, 0], [2, 1], [.01, .15]],
             [[0, 0], [2, 0], [1.9, 1], [0, .8]]]
    for index, points in enumerate(quads):
        vertices = np.asarray(points, dtype=float)
        meshes = []
        for name, faces in [("对角线02", [[0, 1, 2], [0, 2, 3]]),
                            ("对角线13", [[0, 1, 3], [1, 2, 3]])]:
            mesh = trimesh.creation.extrude_triangulation(vertices, np.asarray(faces), height=1)
            path = output / f"凸柱体{index + 1:02d}-{name}.obj"
            assert mesh.is_watertight and mesh.is_winding_consistent
            write_mesh(mesh, path)
            meshes.append({"id": name, "mesh": path.name, "sha256": digest(path),
                           "volume_mm3": float(mesh.volume)})
        assert abs(meshes[0]["volume_mm3"] - meshes[1]["volume_mm3"]) <= 1e-12
        tools = []
        for name, center in [("对角线交会", [1, .5, 1.1]), ("近边交会", [.2, .2, 1.1])]:
            tool = trimesh.creation.icosphere(subdivisions=3, radius=.35)
            tool.apply_translation(center)
            path = output / f"凸柱体{index + 1:02d}-{name}-工具.obj"
            write_mesh(tool, path)
            tools.append({"id": name, "mesh": path.name, "sha256": digest(path),
                          "reference": "实际离散闭合工具，不把球面近似当作精确球"})
        manifest["pairs"].append({"id": f"同几何对角线{index + 1:02d}",
                                  "polygon_xy_mm": points, "meshes": meshes, "tools": tools})
    (output / "01-同几何因果测试清单.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"pairs": len(build(args.output)["pairs"])}, ensure_ascii=False))
