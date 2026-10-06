"""固定旧自交负例与合法归一化候选的GPU场诊断，不执行完整求解。"""

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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.inputs.read_text("utf8"))
    if sha(torchcumesh2sdf.__file__) != "c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad":
        raise ValueError("作者SDF扩展摘要改变")
    checker = "/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646"
    if sha(checker) != "0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3":
        raise ValueError("精确检查器摘要改变")
    args.output.mkdir(exist_ok=False)
    fields, rows = [], []
    for name in ("control", "candidate"):
        path = args.inputs.parent / config[name]["file"]
        if sha(path) != config[name]["sha256"]:
            raise ValueError("实际GPU归一化输入摘要错误")
        checked = subprocess.run([checker, str(path)], capture_output=True, text=True, check=True)
        embedding = json.loads(checked.stdout)
        # 旧非法源仅作已声明的场诊断控制；候选必须合法，双方都不进入完整求解。
        if name == "candidate" and not embedding["embedded_closed"]:
            raise ValueError("新归一化候选不能进入GPU场对照")
        if embedding["self_intersection_pairs"] != config[name]["expected_intersections"]:
            raise ValueError("归一化输入嵌入状态与执行前绑定不同")
        mesh = trimesh.load(path, force="mesh", process=False)
        array = np.ascontiguousarray(mesh.vertices[mesh.faces], np.float32)
        if not np.array_equal(array.astype(np.float64), mesh.vertices[mesh.faces]):
            raise ValueError("GPU场源无法无损转为FP32")
        field = torchcumesh2sdf.get_sdf(torch.from_numpy(array).cuda(), config["R"], config["band"])
        torch.cuda.synchronize()
        values = field.cpu().numpy()
        fields.append(values)
        rows.append({"variant": name, "source_sha256": sha(path), "embedding": embedding,
                     "array_sha256": hashlib.sha256(array.tobytes()).hexdigest(),
                     "field_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
                     "nonfinite_cells": int(np.sum(~np.isfinite(values))),
                     "negative_cells": int(np.sum(values < 0))})
    old, new = fields
    finite = np.isfinite(old) & np.isfinite(new)
    delta = np.abs(old.astype(np.float64) - new.astype(np.float64))
    shifted_old, shifted_new = old - .9 / config["R"], new - .9 / config["R"]
    report = {"生成时间": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "修改时间及修改内容": "首次生成，两个实际SDF核调用，无完整PaMO",
              "文档概述": "旧三对自交控制与单次FP32归一化合法候选的场比较",
              "索引目录": ["rows", "comparison"], "rows": rows, "inputs_sha256": sha(args.inputs),
              "R": config["R"], "band": config["band"], "GPU": torch.cuda.get_device_name(0),
              "SDF_calls": 2, "full_PaMO_calls": 0, "control_is_known_invalid_research_probe": True,
              "comparison": {"total_cells": int(old.size), "both_finite_cells": int(finite.sum()),
                  "changed_cells": int(np.sum(old != new)),
                  "max_difference_finite": float(delta[finite].max()),
                  "max_difference_mapped_mm": float(delta[finite].max() * config["margin"] * config["maximum_span_mm"]),
                  "sign_changes": int(np.sum((old < 0) != (new < 0))),
                  "sign_changes_after_original_offset": int(np.sum((shifted_old < 0) != (shifted_new < 0))),
                  "difference_quantiles_finite": np.quantile(delta[finite], [.5, .95, .99, 1]).tolist()}}
    np.savez_compressed(args.output / "01-两份实际GPU符号场.npz", control=old, candidate=new)
    report["saved_fields_sha256"] = sha(args.output / "01-两份实际GPU符号场.npz")
    (args.output / "02-归一化精度实际GPU场对照.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf8")
    print(json.dumps(report["comparison"]), flush=True)


if __name__ == "__main__":
    main()
