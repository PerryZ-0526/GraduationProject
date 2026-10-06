"""比较实际归一化源整理前后的GPU符号场，不执行完整PaMO。"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone, timedelta

import numpy as np
import torch
import torchcumesh2sdf
import trimesh
from normalized_sdf_chain import canonical_normalized_chain


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text("utf8"))
    expected = next(r["sha256"] for r in metadata["rows"] if r["file"] == "03-CPU归一化SDF源.obj")
    if sha(args.source) != expected:
        raise ValueError("实际归一化输入摘要改变")
    if sha(torchcumesh2sdf.__file__) != "c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad":
        raise ValueError("作者SDF扩展摘要改变")
    args.output.mkdir(exist_ok=False)
    mesh = trimesh.load(args.source, force="mesh", process=False)
    triangles = np.ascontiguousarray(mesh.vertices[mesh.faces], dtype=np.float32)
    if not np.array_equal(triangles.astype(np.float64), mesh.vertices[mesh.faces]):
        raise ValueError("捕获数据不能无损还原FP32")
    vertices, faces, cleaned, chain = canonical_normalized_chain(triangles)
    candidate = args.output / "01-整理后归一化源.obj"
    # 使用17位数字保存实际浮点值，精确检查覆盖真正送入SDF的三角面。
    with candidate.open("w", encoding="utf8") as stream:
        for vertex in vertices:
            stream.write("v " + " ".join(format(float(x), ".17g") for x in vertex) + "\n")
        for face in faces:
            stream.write("f " + " ".join(str(int(x) + 1) for x in face) + "\n")
    checker = "/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646"
    if sha(checker) != "0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3":
        raise ValueError("精确检查器摘要改变")
    checked = subprocess.run([checker, str(candidate)], capture_output=True, text=True, check=True)
    embedding = json.loads(checked.stdout)
    if not embedding["embedded_closed"]:
        raise ValueError("整理后实际SDF源不是合法闭合嵌入")
    fields, rows = [], []
    for name, array in [("original", triangles), ("canonical", cleaned)]:
        # 原扩展要求CUDA张量；两份数组无数值转换地上传，成功源也独立调用两次。
        tensor = torch.from_numpy(array).cuda()
        field = torchcumesh2sdf.get_sdf(tensor, metadata["R"], metadata["band"])
        torch.cuda.synchronize()
        values = field.cpu().numpy() if isinstance(field, torch.Tensor) else np.asarray(field)
        fields.append(values)
        rows.append({"variant": name, "input_array_sha256": hashlib.sha256(array.tobytes()).hexdigest(),
                     "field_array_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
                     "shape": list(values.shape), "dtype": str(values.dtype),
                     "nonfinite_cells": int(np.sum(~np.isfinite(values))),
                     "negative_cells": int(np.sum(values < 0)),
                     "negative_cells_after_author_offset": int(np.sum(values - .9 / metadata["R"] < 0))})
    old, new = fields
    finite = np.isfinite(old) & np.isfinite(new)
    delta = np.abs(old.astype(np.float64) - new.astype(np.float64))
    report = {"生成时间": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "修改时间及修改内容": "首次生成，冻结两次SDF核对照，不执行完整算法",
              "文档概述": "实际归一化源的精确有向面链整理与GPU数值场比较",
              "索引目录": ["chain", "embedding", "rows", "comparison"],
              "source_sha256": sha(args.source), "metadata_sha256": sha(args.metadata),
              "canonical_obj_sha256": sha(candidate), "chain": chain, "embedding": embedding,
              "GPU": torch.cuda.get_device_name(0), "SDF_calls": 2, "full_PaMO_calls": 0,
              "rows": rows, "comparison": {"changed_cells": int(np.sum(old != new)),
                  "both_finite_cells": int(np.sum(finite)), "total_cells": int(old.size),
                  "max_absolute_difference_on_finite_cells": float(delta[finite].max()),
                  "max_difference_mapped_mm": float(delta[finite].max() * metadata["margin"] * metadata["maximum_span_mm"]),
                  "sign_changes": int(np.sum((old < 0) != (new < 0))),
                  "sign_changes_after_author_offset": int(np.sum((old - .9 / metadata["R"] < 0) != (new - .9 / metadata["R"] < 0)))}}
    np.savez_compressed(args.output / "02-两份实际GPU符号场.npz", original=old, canonical=new)
    report["fields_npz_sha256"] = sha(args.output / "02-两份实际GPU符号场.npz")
    (args.output / "03-符号场对照记录.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf8")
    print(json.dumps(report["comparison"]), flush=True)


if __name__ == "__main__":
    main()
