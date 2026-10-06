"""同步计时PaMO安全投影的BVH构建、更新和查询，不改作者计算条件。"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

import torch
import trimesh
import warp as wp

from pamo import PaMO
import pamo_safe_project.energy as energy_module
import pamo_safe_project.system as system_module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    samples: dict[str, list[float]] = defaultdict(list)
    contacts: list[int] = []

    def measure(name: str, action):
        wp.synchronize()
        before = perf_counter()
        result = action()
        wp.synchronize()
        samples[name].append((perf_counter() - before) * 1000.0)
        return result

    original_bvh = wp.Bvh
    original_mesh = wp.Mesh
    bvh_count = 0
    mesh_count = 0

    def measured_bvh(*values, **options):
        nonlocal bvh_count
        bvh_count += 1
        return measure(f"build_bvh_{bvh_count}", lambda: original_bvh(*values, **options))

    def measured_mesh(*values, **options):
        nonlocal mesh_count
        mesh_count += 1
        return measure(f"build_mesh_bvh_{mesh_count}", lambda: original_mesh(*values, **options))

    wp.Bvh = measured_bvh
    wp.Mesh = measured_mesh
    register_active = False

    def wrap_bounds(name: str) -> None:
        original = getattr(system_module, name)

        def measured(*values, **options):
            if register_active:
                return measure("build_" + name, lambda: original(*values, **options))
            return original(*values, **options)

        setattr(system_module, name, measured)

    wrap_bounds("compute_edge_bounds")
    wrap_bounds("compute_tri_bounds")

    def wrap_method(cls, name: str, label: str) -> None:
        original = getattr(cls, name)

        def measured(self, *values, **options):
            return measure(label, lambda: original(self, *values, **options))

        setattr(cls, name, measured)

    original_register = system_module.Stage3System.register_mesh

    def measured_register(self, *values, **options):
        nonlocal register_active
        register_active = True
        try:
            return measure("register_mesh_total", lambda: original_register(self, *values, **options))
        finally:
            register_active = False

    system_module.Stage3System.register_mesh = measured_register
    wrap_method(system_module.Stage3System, "_refit_edge_bvh", "update_edge_bvh")
    wrap_method(system_module.Stage3System, "_refit_tri_bvh", "update_tri_bvh")
    wrap_method(energy_module.Mesh2GTDistanceBvhEnergyCalculator, "update_target", "query_target_bvh")
    original_detect = energy_module.CollisionBvhEnergyCalculator.detect_contact

    def measured_detect(self, *values, **options):
        result = measure("query_contact_bvh", lambda: original_detect(self, *values, **options))
        contacts.append(int(self.contact_counter.numpy()[0]))
        return result

    energy_module.CollisionBvhEnergyCalculator.detect_contact = measured_detect

    mesh = trimesh.load(args.input, force="mesh", process=False)
    before = perf_counter()
    model = PaMO(mesh, use_stage1=True, use_stage3=True)
    construct_ms = (perf_counter() - before) * 1000.0
    vertices = torch.from_numpy(mesh.vertices).float().cuda()
    faces = torch.from_numpy(mesh.faces).int().cuda()
    torch.cuda.synchronize()
    before = perf_counter()
    final_vertices, final_faces = model.run(vertices, faces, min_verts=0, ratio=1.0)
    torch.cuda.synchronize()
    run_ms = (perf_counter() - before) * 1000.0
    mesh_path = args.output / "mesh.obj"
    trimesh.Trimesh(vertices=final_vertices, faces=final_faces).export(mesh_path)
    record = {
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        "author_system_sha256": hashlib.sha256(Path(system_module.__file__).read_bytes()).hexdigest(),
        "author_energy_sha256": hashlib.sha256(Path(energy_module.__file__).read_bytes()).hexdigest(),
        "construct_ms": construct_ms,
        "run_ms": run_ms,
        "contact_count_max": max(contacts) if contacts else None,
        "contact_count_min": min(contacts) if contacts else None,
        "operations": {
            name: {"count": len(values), "sum_ms": sum(values),
                   "mean_ms": sum(values) / len(values), "max_ms": max(values)}
            for name, values in samples.items()
        },
    }
    (args.output / "profile.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
