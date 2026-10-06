"""仅捕获未接受修复候选的FP64三角均值原点编码，禁止计作发布或完整PaMO。"""

import argparse
import hashlib
import inspect
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import torch
import pamo
import trimesh


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_obj(path, vertices, faces):
    # 17位有效数字保留捕获的二进制浮点值，不焊接顶点或改变面索引。
    with path.open("w", encoding="utf8") as stream:
        for vertex in vertices:
            stream.write("v " + " ".join(format(float(x), ".17g") for x in vertex) + "\n")
        for face in faces:
            stream.write("f " + " ".join(str(int(x) + 1) for x in face) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    author = Path(inspect.getfile(pamo.PaMO))
    if sha(author) != "0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a":
        raise ValueError("作者预处理源码改变")
    args.output.mkdir(exist_ok=False)
    source = trimesh.load(args.source, force="mesh", process=False)
    tool = trimesh.load(args.tool, force="mesh", process=False)
    origin = np.asarray(source.vertices[source.faces], np.float64).mean(axis=1).mean(axis=0)
    local = source.copy()
    local.vertices = np.asarray(source.vertices, np.float64) - origin
    points = torch.from_numpy(np.asarray(local.vertices, np.float32)).cuda()
    faces = torch.from_numpy(np.asarray(local.faces, np.int32)).cuda()
    model = pamo.PaMO(local, use_stage1=True, use_stage3=True)
    normalized, minimum, maximum, mean = model.preprocess_mesh(points, faces, model.band, model.margin)
    centered = points - torch.from_numpy(mean).to(points.device)
    initial_cpu, centered_cpu = points.cpu().numpy(), centered.cpu().numpy()
    indices = faces.cpu().numpy()
    # 从逐面SDF数组恢复同一顶点表，严格核对共享顶点各次出现的值一致。
    flat_ids = indices.reshape(-1)
    normalized_vertices = np.empty_like(initial_cpu)
    normalized_vertices[flat_ids] = normalized.reshape(-1, 3)
    if len(np.unique(flat_ids)) != len(initial_cpu) or not np.array_equal(normalized_vertices[indices], normalized):
        raise ValueError("归一化SDF源不能按原拓扑恢复共享顶点，停止捕获")
    rows = []
    for name, vertices in [("01-CUDA初始编码源.obj", initial_cpu),
                           ("02-CUDA再中心化源.obj", centered_cpu),
                           ("03-CPU归一化SDF源.obj", normalized_vertices)]:
        path = args.output / name
        write_obj(path, vertices, indices)
        triangles = vertices[indices]
        zero = int(np.sum(np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0],
                                                  triangles[:, 2] - triangles[:, 0]), axis=1) == 0))
        rows.append({"file": name, "sha256": sha(path), "native_FP32_zero_area_faces": zero})
    record = {"生成时间": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "修改时间及修改内容": "首次生成，保留实际工作源浮点值与原拓扑",
              "文档概述": "实际GPU预处理源捕获，不调用完整PaMO",
              "索引目录": ["scope", "rows"],
              "scope": "unaccepted_repair_candidate_actual_GPU_preprocessing_only_no_full_PaMO", "origin_rule": "FP64_mean_of_triangle_centroids", "source_sha256": sha(args.source),
              "tool_sha256": sha(args.tool), "author_sha256": sha(author), "origin_mm": origin.tolist(),
              "R": model.R, "band": model.band, "margin": model.margin,
              "mean_local_mm": mean.tolist(), "minimum_centered_mm": minimum.tolist(), "maximum_span_mm": float(maximum),
              "all_stored_values_are_actual_FP32": True, "rows": rows}
    (args.output / "04-实际GPU工作源捕获记录.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), "utf8")
    print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
