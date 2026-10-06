"""追踪PaMO已捕获CUDA图中的一次CG求解，定位实际GPU核函数耗时。"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

import torch
from torch.profiler import profile, ProfilerActivity
import trimesh

from pamo import PaMO
from pamo_safe_project.cg_solver import CGSolver


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    original_solve = CGSolver.solve
    solve_count = 0
    traced: dict = {}

    def measured_solve(self):
        nonlocal solve_count
        solve_count += 1
        if solve_count != 2:
            return original_solve(self)
        torch.cuda.synchronize()
        started = perf_counter()
        with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as trace:
            result = original_solve(self)
            torch.cuda.synchronize()
        wall_ms = (perf_counter() - started) * 1000.0
        groups: dict[str, list[float]] = defaultdict(list)
        cuda_events = 0
        for event in trace.events():
            if str(event.device_type).endswith("CUDA"):
                cuda_events += 1
                groups[event.name].append(float(event.device_time_total) / 1000.0)
        traced.update({
            "cg_solve_index": solve_count,
            "cg_wall_with_profiler_ms": wall_ms,
            "cuda_event_count": cuda_events,
            "gpu_kernel_groups": [
                {"name": name, "calls": len(values), "total_gpu_ms": sum(values),
                 "mean_gpu_ms": sum(values) / len(values)}
                for name, values in sorted(groups.items(), key=lambda item: -sum(item[1]))
            ],
            "stage3_particles": self.system.n_particles,
            "stage3_edges": self.system.n_edges,
            "stage3_triangles": self.system.n_triangles,
            "max_particles": self.system.config.max_particles,
            "max_blocks": self.system.config.max_blocks,
        })
        return result

    CGSolver.solve = measured_solve
    mesh = trimesh.load(args.input, force="mesh", process=False)
    model = PaMO(mesh, use_stage1=True, use_stage3=True)
    vertices = torch.from_numpy(mesh.vertices).float().cuda()
    faces = torch.from_numpy(mesh.faces).int().cuda()
    torch.cuda.synchronize()
    started = perf_counter()
    final_vertices, final_faces = model.run(vertices, faces, min_verts=0, ratio=1.0)
    torch.cuda.synchronize()
    run_ms = (perf_counter() - started) * 1000.0
    mesh_path = args.output / "mesh.obj"
    trimesh.Trimesh(vertices=final_vertices, faces=final_faces).export(mesh_path)
    report = {
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        "cg_source_sha256": hashlib.sha256(Path(original_solve.__code__.co_filename).read_bytes()).hexdigest(),
        "run_ms": run_ms,
        "solve_count": solve_count,
        "trace": traced,
    }
    (args.output / "profile.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_ms": run_ms, "trace": traced}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
