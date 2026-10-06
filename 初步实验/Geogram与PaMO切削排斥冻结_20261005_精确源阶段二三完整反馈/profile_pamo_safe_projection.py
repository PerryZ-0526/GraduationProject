"""对作者安全投影逐操作同步计时，保留其原有计算路径。"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
from pathlib import Path
import textwrap
from time import perf_counter

import torch
import trimesh
import warp as wp

from pamo import PaMO
import pamo_safe_project.system as system_module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)

    original_source = textwrap.dedent(inspect.getsource(system_module.Stage3System.step))
    source_hash = hashlib.sha256(original_source.encode()).hexdigest()
    source = original_source
    substitutions = (
        ("        self._update_vertex_target()\n", "        self._update_vertex_target()\n        profile_mark('target')\n"),
        ("            self._detect_contact()\n", "            self._detect_contact()\n            profile_mark('contact_step')\n"),
        ("                self._detect_contact()\n", "                self._detect_contact()\n                profile_mark('contact_newton')\n"),
        ("            self._compute_energy()\n", "            self._compute_energy()\n            profile_mark('energy')\n"),
        ("            self._compute_diff()\n", "            self._compute_diff()\n            profile_mark('gradient')\n"),
        ("            self.cg_solver.solve()\n", "            self.cg_solver.solve()\n            profile_mark('cg_solve')\n"),
        ("            self._clamp_p()\n", "            self._clamp_p()\n            profile_mark('clamp')\n"),
        ("            self._ccd()\n", "            self._ccd()\n            profile_mark('ccd')\n"),
        ("                wp.capture_launch(self.line_search_graph)\n", "                wp.capture_launch(self.line_search_graph)\n                profile_mark('line_search')\n"),
        ("                self._line_search()\n", "                self._line_search()\n                profile_mark('line_search')\n"),
    )
    for old, new in substitutions:
        old = "\n".join(line[4:] if line.startswith("    ") else line for line in old.split("\n"))
        new = "\n".join(line[4:] if line.startswith("    ") else line for line in new.split("\n"))
        if source.count("\n" + old) != 1:
            raise ValueError(f"作者源码锚点变化: {old.strip()}")
        source = source.replace("\n" + old, "\n" + new)
    if source.count("\n    self._update_vertex_target()\n") != 1:
        raise ValueError("目标更新锚点异常")
    source = source.replace("\n    self._update_vertex_target()\n",
                            "\n    profile_mark('step_start')\n    self._update_vertex_target()\n")

    samples: dict[str, list[float]] = defaultdict(list)
    last_time: float | None = None

    def profile_mark(label: str) -> None:
        nonlocal last_time
        wp.synchronize()
        now = perf_counter()
        if last_time is not None:
            samples[label].append((now - last_time) * 1000.0)
        last_time = now

    namespace = dict(vars(system_module))
    namespace["profile_mark"] = profile_mark
    exec(compile(source, str(Path(system_module.__file__)), "exec"), namespace)
    system_module.Stage3System.step = namespace["step"]

    outer_samples: dict[str, list[float]] = defaultdict(list)

    def wrap_method(name: str) -> None:
        original = getattr(system_module.Stage3System, name)

        def measured(self, *method_args, **method_kwargs):
            wp.synchronize()
            before = perf_counter()
            result = original(self, *method_args, **method_kwargs)
            wp.synchronize()
            outer_samples[name].append((perf_counter() - before) * 1000.0)
            return result

        setattr(system_module.Stage3System, name, measured)

    for method_name in ("register_mesh", "get_vertices", "clear"):
        wrap_method(method_name)

    mesh = trimesh.load(args.input, force="mesh", process=False)
    construct_start = perf_counter()
    model = PaMO(mesh, use_stage1=True, use_stage3=True)
    construct_ms = (perf_counter() - construct_start) * 1000.0
    vertices = torch.from_numpy(mesh.vertices).float().cuda()
    faces = torch.from_numpy(mesh.faces).int().cuda()
    torch.cuda.synchronize()
    start = perf_counter()
    final_vertices, final_faces = model.run(vertices, faces, min_verts=0, ratio=1.0)
    torch.cuda.synchronize()
    run_ms = (perf_counter() - start) * 1000.0
    output = args.output / "mesh.obj"
    trimesh.Trimesh(vertices=final_vertices, faces=final_faces).export(output)
    record = {
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "author_step_source_sha256": source_hash,
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "construct_ms": construct_ms,
        "run_ms": run_ms,
        "outer_operation_ms": {
            name: {"count": len(values), "sum": sum(values), "max": max(values)}
            for name, values in outer_samples.items()
        },
        "synchronized_operation_ms": {
            name: {"count": len(values), "sum": sum(values),
                   "mean": sum(values) / len(values), "max": max(values)}
            for name, values in samples.items()
        },
    }
    (args.output / "profile.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
