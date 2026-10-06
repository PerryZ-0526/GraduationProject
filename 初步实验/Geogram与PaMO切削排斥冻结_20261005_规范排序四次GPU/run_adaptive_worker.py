"""独立CUDA进程执行接缝尺度匹配和整网格安全投影。"""

import argparse
import json
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh
from adaptive_seam import generate_adaptive_quality
from constrained_quality import safe_project, fixed_surface_contract
from locality_masks import save_obj_fp64


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "tool", "executable", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--method", required=True)
    args = parser.parse_args()
    source = trimesh.load(args.source, force="mesh", process=False)
    tool = trimesh.load(args.tool, force="mesh", process=False)
    bits = json.loads(args.labels.read_text())["operand_bits"]
    started = perf_counter()
    if args.method == "full":
        from locality_gpu import run_full
        args.output.mkdir(parents=True)
        result, details = run_full(source)
    else:
        prepared, mesh, ids, fixed, active, required, details = generate_adaptive_quality(
            source, bits, tool, args.output, args.executable, planar_pass=args.method in ("adaptive_planar", "expanded"),
            rings=4 if args.method == "expanded" else 2)
        save_obj_fp64(mesh, args.output / "before_projection.obj")
        result, projection = safe_project(prepared, mesh, ids, fixed)
        details.update(projection)
        details["fixed_contract"] = fixed_surface_contract(prepared, result, active, required)
        if not details["fixed_contract"]["passed"]:
            raise RuntimeError("GPU投影破坏固定外部")
    if not np.isfinite(result.vertices).all() or np.any(result.area_faces <= 1e-12):
        raise RuntimeError("非有限或退化输出")
    save_obj_fp64(result, args.output / "candidate.obj")
    details.update(method=args.method, maintenance_ms=(perf_counter() - started) * 1000, status="pending_independent_audit")
    (args.output / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
