"""将共同解析输入适配到Geogram作者精确网格CSG实现。"""
from hashlib import sha256
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np
import pyvista as pv
import trimesh

from surface_methods import _axis, plane_height


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
DEFAULT_BINARY = PROJECT_ROOT / "tmp" / "geogram" / "geogram_boolean"
GEOGRAM_COMMIT = "130442ff0f0c069d48ab4ebb4012218f3d861cf2"
TOOL_SUBDIVISIONS = 3


def _export_double_obj(path, mesh):
    with Path(path).open("w", encoding="ascii") as output:
        for vertex in np.asarray(mesh.vertices):
            output.write(
                "v " + " ".join(format(float(value), ".17g") for value in vertex)
                + "\n"
            )
        for face in np.asarray(mesh.faces):
            output.write(
                "f " + " ".join(str(int(value) + 1) for value in face) + "\n"
            )


def _distance_to_segment(points, start, end):
    points = np.asarray(points, dtype=np.float64)
    start = np.asarray(start, dtype=np.float64)
    end = np.asarray(end, dtype=np.float64)
    delta = end - start
    squared_length = float(delta @ delta)
    if squared_length == 0.0:
        return np.linalg.norm(points - start, axis=-1)
    parameter = np.clip(
        np.sum((points - start) * delta, axis=-1) / squared_length,
        0.0,
        1.0,
    )
    nearest = start + parameter[..., None] * delta
    return np.linalg.norm(points - nearest, axis=-1)


def _capsule_contains(outer, inner, tolerance=1e-12):
    endpoint_distance = _distance_to_segment(
        np.stack((inner["start"], inner["end"])),
        outer["start"],
        outer["end"],
    )
    return bool(
        np.max(endpoint_distance) + float(inner["radius"])
        <= float(outer["radius"]) + tolerance
    )


def effective_primitives(primitives):
    """去除被其他胶囊完全包含的起点球和重复路径原语。"""
    retained = []
    removed = []
    for index, primitive in enumerate(primitives):
        redundant = False
        for other_index, other in enumerate(primitives):
            if index == other_index or not _capsule_contains(other, primitive):
                continue
            mutually_contained = _capsule_contains(primitive, other)
            if not mutually_contained or other_index < index:
                redundant = True
                break
        if redundant:
            removed.append(primitive["event_id"])
        else:
            retained.append(primitive)
    return retained, removed


def _slab_mesh(case, xy_bounds, bottom_z, spacing):
    x = _axis(xy_bounds[:2], spacing)
    y = _axis(xy_bounds[2:], spacing)
    xy = np.stack(np.meshgrid(x, y, indexing="ij"), axis=-1)
    top = np.column_stack((xy.reshape(-1, 2), plane_height(xy, case).reshape(-1)))
    bottom = np.column_stack(
        (
            xy.reshape(-1, 2),
            np.full(xy.shape[0] * xy.shape[1], bottom_z),
        )
    )
    points = np.vstack((top, bottom))
    top_count = len(top)
    ny = len(y)
    faces = []
    for i in range(len(x) - 1):
        for j in range(len(y) - 1):
            lower_left = i * ny + j
            lower_right = (i + 1) * ny + j
            upper_right = (i + 1) * ny + j + 1
            upper_left = i * ny + j + 1
            faces.extend(
                (
                    [lower_left, lower_right, upper_right],
                    [lower_left, upper_right, upper_left],
                    [
                        top_count + lower_left,
                        top_count + upper_right,
                        top_count + lower_right,
                    ],
                    [
                        top_count + lower_left,
                        top_count + upper_left,
                        top_count + upper_right,
                    ],
                )
            )

    boundary = []
    for i in range(len(x) - 1):
        boundary.append((i * ny, (i + 1) * ny))
    for j in range(len(y) - 1):
        boundary.append(((len(x) - 1) * ny + j, (len(x) - 1) * ny + j + 1))
    for i in range(len(x) - 1, 0, -1):
        boundary.append((i * ny + len(y) - 1, (i - 1) * ny + len(y) - 1))
    for j in range(len(y) - 1, 0, -1):
        boundary.append((j, j - 1))
    for first, second in boundary:
        faces.extend(
            (
                [first, top_count + first, top_count + second],
                [first, top_count + second, second],
            )
        )
    mesh = trimesh.Trimesh(
        vertices=points,
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError("Geogram初始平面厚片必须闭合且绕序一致")
    return mesh


def _capsule_mesh(primitive, subdivisions=TOOL_SUBDIVISIONS):
    sphere = trimesh.creation.icosphere(
        subdivisions=subdivisions,
        radius=1.0,
    )
    start = np.asarray(primitive["start"], dtype=np.float64)
    end = np.asarray(primitive["end"], dtype=np.float64)
    radius = float(primitive["radius"])
    if np.linalg.norm(start - end) <= 1e-14:
        return trimesh.Trimesh(
            vertices=np.asarray(sphere.vertices) * radius + start,
            faces=np.asarray(sphere.faces),
            process=False,
        )
    points = np.vstack(
        (
            np.asarray(sphere.vertices) * radius + start,
            np.asarray(sphere.vertices) * radius + end,
        )
    )
    return trimesh.convex.convex_hull(points)


def _top_surface(mesh):
    triangles = np.asarray(mesh.triangles, dtype=np.float64)
    normals = np.cross(
        triangles[:, 1] - triangles[:, 0],
        triangles[:, 2] - triangles[:, 0],
    )
    lengths = np.linalg.norm(normals, axis=1)
    normals = np.divide(
        normals,
        lengths[:, None],
        out=np.zeros_like(normals),
        where=lengths[:, None] > 0,
    )
    selected = np.flatnonzero(normals[:, 2] > 1e-8)
    surface = mesh.submesh([selected], append=True, repair=False)
    return pv.PolyData(
        np.asarray(surface.vertices, dtype=np.float64),
        np.column_stack(
            (
                np.full(len(surface.faces), 3, dtype=np.int64),
                np.asarray(surface.faces, dtype=np.int64),
            )
        ),
    )


def geogram_surface(
    case,
    replay,
    xy_bounds,
    z_bounds,
    spacing,
    work_directory,
    binary=DEFAULT_BINARY,
    tool_subdivisions=TOOL_SUBDIVISIONS,
    deduplicate_contained=True,
    no_simplify=False,
    timeout_s=60,
):
    """顺序执行去重后的胶囊差集并返回朝上的开放表面。"""
    binary = Path(binary).resolve()
    if not binary.is_file():
        raise FileNotFoundError(f"缺少Geogram适配器: {binary}")
    work_directory = Path(work_directory)
    work_directory.mkdir(parents=True, exist_ok=True)
    initial = _slab_mesh(case, xy_bounds, float(z_bounds[0]), spacing)
    previous_path = work_directory / "initial.obj"
    _export_double_obj(previous_path, initial)

    if deduplicate_contained:
        primitives, removed_ids = effective_primitives(replay["primitives"])
    else:
        primitives = list(replay["primitives"])
        removed_ids = []
    step_rows = []
    started = perf_counter()
    for index, primitive in enumerate(primitives):
        tool_path = work_directory / f"tool_{index}.obj"
        output_path = work_directory / f"difference_{index}.obj"
        log_path = work_directory / f"difference_{index}.log"
        tool = _capsule_mesh(primitive, subdivisions=tool_subdivisions)
        _export_double_obj(tool_path, tool)
        step_started = perf_counter()
        command = [str(binary)]
        if no_simplify:
            command.append("--no-simplify")
        command.extend((str(previous_path), str(tool_path), str(output_path)))
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        log_path.write_text(
            completed.stdout + completed.stderr,
            encoding="utf-8",
        )
        if completed.returncode:
            raise RuntimeError(
                f"Geogram差集{primitive['event_id']}失败，返回码"
                f"{completed.returncode}"
            )
        step_rows.append(
            {
                "event_id": primitive["event_id"],
                "elapsed_ms": (perf_counter() - step_started) * 1000.0,
                "input_faces": int(len(tool.faces)),
                "command": command,
                "output": output_path.name,
                "log": log_path.name,
            }
        )
        previous_path = output_path

    full_mesh = trimesh.load(previous_path, force="mesh", process=False)
    surface = _top_surface(full_mesh)
    return surface, {
        "implementation": (
            "Geogram mesh_difference, "
            + (
                "MESH_BOOL_OPS_NO_SIMPLIFY"
                if no_simplify
                else "MESH_BOOL_OPS_DEFAULT"
            )
        ),
        "paper": "Exact predicates, exact constructions and combinatorics for mesh CSG",
        "venue": "ACM Transactions on Graphics 2025 (CCF-A)",
        "doi": "10.1145/3744642",
        "repository": "https://github.com/BrunoLevy/geogram",
        "commit": GEOGRAM_COMMIT,
        "license": "BSD-3-Clause",
        "binary": str(binary),
        "binary_sha256": sha256(binary.read_bytes()).hexdigest(),
        "tool_discretization": f"icosphere subdivisions={tool_subdivisions}",
        "tool_subdivisions": tool_subdivisions,
        "deduplicate_contained": deduplicate_contained,
        "no_simplify": no_simplify,
        "timeout_s": timeout_s,
        "input_primitive_count": len(replay["primitives"]),
        "effective_primitive_count": len(primitives),
        "redundant_contained_event_ids": removed_ids,
        "steps": step_rows,
        "final_full_mesh": str(previous_path),
        "elapsed_ms": (perf_counter() - started) * 1000.0,
        "full_solid_watertight": bool(full_mesh.is_watertight),
        "full_solid_winding_consistent": bool(full_mesh.is_winding_consistent),
        "full_solid_euler_number": int(full_mesh.euler_number),
        "scope": (
            "作者精确网格CSG作用于离散三角工具和闭合平面厚片；"
            "精确谓词不消除工具离散误差，也不自动保证输出三角形质量"
        ),
    }
