"""固定顶点的交叠区域翻边诊断，至多三轮每轮十二个实际候选。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference as vtk_reference

from run_reference_cut_feedback import ReferenceCutEngine
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256
from locality_masks import save_obj_fp64
from run_constrained_feedback import global_geometry
from geometry_preservation_audit import MeshDistance, as_polydata
from audit_pamo_outputs import area_samples


def flip_candidate(mesh, owners, edge):
    """保持局部链接和绕序，禁止重复对角线及新增退化面；非共面改动由完整距离审查。"""
    i, j = map(int, owners)
    a, b = map(int, edge)
    first, second = mesh.faces[[i, j]]
    if not any(first[k] == a and first[(k + 1) % 3] == b for k in range(3)):
        a, b = b, a
    c = next(int(v) for v in first if v not in (a, b))
    d = next(int(v) for v in second if v not in (a, b))
    if c == d or not any(second[k] == b and second[(k + 1) % 3] == a for k in range(3)):
        return None
    if np.any(np.sum(np.isin(mesh.faces, [c, d]), axis=1) == 2):
        return None
    replacement = np.array([[c, d, b], [d, c, a]])
    old = mesh.triangles[[i, j]]
    normal = np.cross(old[:, 1] - old[:, 0], old[:, 2] - old[:, 0]).sum(axis=0)
    new = mesh.vertices[replacement]
    normals = np.cross(new[:, 1] - new[:, 0], new[:, 2] - new[:, 0])
    if np.any(normals @ normal <= 0):
        return None
    for coordinates in (mesh.vertices, mesh.vertices.astype(np.float32)):
        tri = coordinates[replacement]
        area2 = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
        if not np.isfinite(area2).all() or np.any(area2 <= 2e-12):
            return None
    result = mesh.copy()
    result.faces[[i, j]] = replacement
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.asset / "01-局部碰撞回退完整负例冻结.json").read_text("utf8"))
    for name, digest in manifest["files"].items():
        if sha256(args.asset / name) != digest:
            raise ValueError("输入资产摘要不符")
    proof = json.loads((args.asset / "02-实际完整嵌入与提案距离证据.json").read_text("utf8"))
    initial = proof["rows"][0]
    working = trimesh.load(args.asset / initial["saved_file"], force="mesh", process=False)
    reference = trimesh.load(args.asset / "独立累计参照.obj", force="mesh", process=True, validate=True)
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    diagnostic = "/root/autodl-tmp/graduation_project/constrained_20261004_FJ3368双向覆盖嵌入诊断_f6e41738c1ef/diagnosis"
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，固定翻边预算先于输出",
        "文档概述": "只作连接诊断，不称来源保持、工具排斥或新GPU父反馈",
        "索引目录": ["rows", "selected"], "status": "running", "new_GPU_calls": 0,
        "round_budget": 3, "candidate_budget_per_round": 12, "vertices_fixed": True,
        "input_manifest_sha256": sha256(args.asset / "01-局部碰撞回退完整负例冻结.json"), "rows": [], "selected": []}
    record = args.output / "01-固定顶点局部翻边与完整嵌入诊断.json"
    save(record, report)
    checks = initial["checks"]
    geometry = initial["geometry"]
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("远端诊断目录已存在")
        if execute(engine.client, ["sha256sum", diagnostic])["stdout"].split()[0] != "0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd":
            raise ValueError("完整定位器摘要不同")
        for round_index in range(3):
            pairs = checks.get("intersection_face_ids", [])
            if len(pairs) != checks["self_intersection_pairs"]:
                report["reason"] = "location_list_incomplete"
                break
            affected = {int(face) for pair in pairs for face in pair}
            if not affected and geometry["probe_max_mm"] > .1:
                # 交叠清零后仍超差时，在同预算内继续处理最差的四个面，不提前停止。
                locator = vtkStaticCellLocator()
                locator.SetDataSet(as_polydata(working))
                locator.BuildLocator()
                nearest, cell, sub, square = [0., 0., 0.], vtk_reference(0), vtk_reference(0), vtk_reference(0.)
                priorities = {}
                for points, distance in ((np.vstack((working.vertices, area_samples(as_polydata(working), 8192, 20260922))),
                                          MeshDistance(as_polydata(reference))),
                                         (np.vstack((reference.vertices, area_samples(as_polydata(reference), 8192, 20260923))),
                                          MeshDistance(as_polydata(working)))):
                    errors = distance(points)
                    for point, error in zip(points[errors > .1], errors[errors > .1]):
                        locator.FindClosestPoint(point, nearest, cell, sub, square)
                        face = int(cell)
                        priorities[face] = max(priorities.get(face, 0.), float(error))
                affected = set(sorted(priorities, key=lambda face: (-priorities[face], face))[:4])
            options = []
            considered = 0
            for owners, edge in zip(working.face_adjacency, working.face_adjacency_edges):
                if not affected.intersection(map(int, owners)):
                    continue
                candidate = flip_candidate(working, owners, edge)
                if candidate is None:
                    continue
                considered += 1
                if considered > 12:
                    break
                name = f"round_{round_index}_candidate_{considered}.obj"
                path = args.output / name
                save_obj_fp64(candidate, path)
                remote = engine.remote + "/" + name
                engine.sftp.put(str(path), remote)
                if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
                    raise ValueError("实际检查保存对象摘要不同")
                execution = execute(engine.client, [diagnostic, remote], timeout=120)
                if execution["returncode"]:
                    raise RuntimeError("完整诊断器异常")
                current = json.loads(execution["stdout"])
                distance = global_geometry(candidate, reference)
                entry = {"round": round_index, "edge": edge.tolist(), "faces": owners.tolist(),
                    "file": name, "saved_sha256": sha256(path), "checks": current, "geometry": distance,
                    "vertices_exact": bool(np.array_equal(candidate.vertices, working.vertices))}
                report["rows"].append(entry)
                save(record, report)
                print(round_index, considered, current["self_intersection_pairs"], distance["probe_max_mm"], flush=True)
                score = (current["self_intersection_pairs"], distance["probe_max_mm"])
                if current.get("topology_valid") and current.get("closed") and score < (checks["self_intersection_pairs"], geometry["probe_max_mm"]):
                    options.append((score, candidate, current, distance, entry))
            if not options:
                report["reason"] = "no_improving_fixed_budget_flip"
                break
            _, working, checks, geometry, entry = min(options, key=lambda item: item[0])
            report["selected"].append(entry)
            if checks["embedded_closed"] and geometry["probe_max_mm"] <= .1:
                report["embedding_and_probe_passed"] = True
                break
        save_obj_fp64(working, args.output / "selected.obj")
        report.update(status="completed", finished_beijing=now(), final_checks=checks, final_geometry=geometry,
            selected_sha256=sha256(args.output / "selected.obj"), tool_exclusion_certified=False)
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
