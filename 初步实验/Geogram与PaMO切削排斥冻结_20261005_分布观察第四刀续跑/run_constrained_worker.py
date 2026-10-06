"""远端单次候选执行；每次独立CUDA进程，产物由本机另行审计。"""

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import trimesh

from locality_masks import save_obj_fp64
from constrained_quality import generate_quality, safe_project, fixed_surface_contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    source = trimesh.load(args.source, force="mesh", process=False)
    tool = trimesh.load(args.tool, force="mesh", process=False)
    bits = json.loads(args.labels.read_text())["operand_bits"]
    started = perf_counter()
    if args.method == "full":
        from locality_gpu import run_full
        result, details = run_full(source)
    else:
        mode = args.method if args.method in ("global", "spatial") else "boolean"
        rings = 0 if args.method == "no_transition" else 4 if args.method == "expanded" else 2
        boundary = args.method != "no_boundary"
        mesh, ids, fixed, active, required_fixed, details = generate_quality(
            source, bits, tool, mode, args.output, args.executable, rings, boundary)
        # 保留投影前快照，避免把质量生成与最后投影的作用混在一起。
        save_obj_fp64(mesh, args.output / "before_projection.obj")
        if args.method != "no_projection":
            result, projection = safe_project(source, mesh, ids, fixed)
            details.update(projection)
        else:
            result = mesh
        details["fixed_contract"] = fixed_surface_contract(source, result, active, required_fixed)
    if not np.isfinite(result.vertices).all() or np.any(result.area_faces <= 1e-12):
        raise RuntimeError("非有限或退化输出")
    save_obj_fp64(result, args.output / "candidate.obj")
    details.update(method=args.method, maintenance_ms=(perf_counter() - started) * 1000,
                   status="pending_independent_audit")
    (args.output / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(details, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
