"""在已见保存帧中寻找维护网格侵入本次凸工具内部的有限探针见证。"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import trimesh


def tool_clearance(points, tool):
    """凸工具内负外正的最大平面值；内部绝对值是最近支撑平面距离。"""
    normals = tool.face_normals
    origin = tool.vertices[tool.faces[:, 0]]
    offsets = np.sum(normals * origin, axis=1)
    return np.concatenate([np.max(batch @ normals.T - offsets, axis=1)
                           for batch in np.array_split(points, max(1, len(points) // 512))])


def main():
    root = Path(__file__).parent
    prepared = root / "实验结果/20261004_局部维护保存帧开发"
    output = root / "实验结果/20261004_已切区域材料回填诊断"
    output.mkdir(exist_ok=True)
    target = output / "01-凸工具内部侵入探针.json"
    if target.exists():
        raise FileExistsError("既有诊断结果禁止覆盖")
    report = {"生成时间": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y年%m月%d日%H时%M分%S秒"),
              "修改时间及修改内容": "首次生成，只读开发输出",
              "文档概述": "本次凸工具对源网格和四种维护输出的顶点及面心探针，非完整材料体积或连续证书",
              "索引目录": ["参数", "结果"], "参数": {"witness_threshold_mm": 1e-7}, "结果": [],
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for folder in sorted(prepared.glob("*/tool.obj")):
        case = folder.parent.name
        tool = trimesh.load(folder, process=False, force="mesh")
        if not tool.is_convex or not tool.is_watertight or not tool.is_winding_consistent:
            raise ValueError("诊断要求闭合、朝向一致的凸工具")
        item = {"case": case, "tool_sha256": hashlib.sha256(folder.read_bytes()).hexdigest(), "methods": {}}
        paths = {"source": folder.parent / "source.obj"}
        for method in ("full", "global", "spatial", "boolean"):
            paths[method] = prepared / f"取回输出/saved_batch_outputs/{case}/r0_{method}.obj"
        for method, path in paths.items():
            if not path.exists():
                item["methods"][method] = {"status": "output_missing"}
                continue
            mesh = trimesh.load(path, process=False, force="mesh")
            points = np.concatenate((mesh.vertices, mesh.triangles_center))
            values = tool_clearance(points, tool)
            minimum = int(np.argmin(values))
            item["methods"][method] = {"status": "probed", "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                        "probes": len(points), "inside_probe_count": int(np.sum(values < -1e-7)),
                                        "max_inward_plane_depth_mm": max(0., -float(values[minimum])),
                                        "deepest_probe_xyz_mm": points[minimum].tolist()}
        report["结果"].append(item)
        print(case, [(name, data.get("inside_probe_count"), data.get("max_inward_plane_depth_mm"))
                     for name, data in item["methods"].items()], flush=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
