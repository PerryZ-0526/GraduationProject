"""同源局部碰撞回退提案诊断，保持全量嵌入检查和固定两轮三提案。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from run_reference_cut_feedback import ReferenceCutEngine
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256
from bidirectional_coverage_exclusion import bidirectional_midpoint_seed
from locality_masks import save_obj_fp64
from run_constrained_feedback import global_geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    inputs = json.loads((args.asset / "01-线性法向限步同源提案冻结.json").read_text("utf8"))
    for name, digest in inputs["files"].items():
        if sha256(args.asset / name) != digest:
            raise ValueError("同源提案资产摘要不同")
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    diagnostic = "/root/autodl-tmp/graduation_project/constrained_20261004_FJ3368双向覆盖嵌入诊断_f6e41738c1ef/diagnosis"
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，固定六提案及全量检查",
        "文档概述": "只诊断局部回退，不称工具排斥或新GPU父反馈通过", "索引目录": ["rows"],
        "new_GPU_calls": 0, "round_budget": 2, "proposals_per_round": 3,
        "tool_exclusion_certified": False, "status": "running", "rows": []}
    record = args.output / "01-同源局部碰撞回退提案与完整嵌入.json"
    save(record, report)
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("诊断远端目录已存在")
        actual = execute(engine.client, ["sha256sum", diagnostic])["stdout"].split()[0]
        if actual != "0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd":
            raise ValueError("已验证完整定位器摘要不同")
        report["diagnostic_sha256"] = actual
        working = trimesh.load(args.asset / "合法恢复基准.obj", force="mesh", process=False)
        reference = trimesh.load(args.asset / "独立累计参照.obj", force="mesh", process=True, validate=True)
        for round_index in range(2):
            seed, coverage = bidirectional_midpoint_seed(working, reference, orientation_limited=True)
            if not coverage["marked_faces"]:
                break
            base_vertices = seed.vertices.copy()
            base_vertices[:len(working.vertices)] = working.vertices
            for vertex, a, b in coverage["refinement"]["midpoint_edges"]:
                base_vertices[vertex] = (working.vertices[a] + working.vertices[b]) * .5
            affected = set()
            legal = []
            for fraction in (1., .5, .25):
                candidate = seed.copy()
                if affected:
                    ids = np.array(sorted(affected), dtype=int)
                    # 只回退实际交叠面的顶点，其余位置沿用完整局部法向提案。
                    candidate.vertices[ids] = base_vertices[ids] + fraction * (seed.vertices[ids] - base_vertices[ids])
                path = args.output / f"round_{round_index}_step_{fraction}.obj"
                save_obj_fp64(candidate, path)
                remote = engine.remote + "/" + path.name
                engine.sftp.put(str(path), remote)
                if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
                    raise ValueError("实际检查对象摘要不同")
                execution = execute(engine.client, [diagnostic, remote], timeout=120)
                if execution["returncode"]:
                    raise RuntimeError("完整定位器未正常执行")
                checks = json.loads(execution["stdout"])
                geometry = global_geometry(candidate, reference)
                report["rows"].append({"round": round_index, "fraction": fraction,
                    "local_backoff_vertices": sorted(affected), "coverage": coverage,
                    "saved_file": path.name, "saved_sha256": sha256(path), "checks": checks,
                    "geometry": geometry, "execution": execution})
                save(record, report)
                print(round_index, fraction, checks["self_intersection_pairs"], geometry["probe_max_mm"], flush=True)
                if checks["embedded_closed"]:
                    legal.append((geometry["probe_max_mm"], candidate, path.name))
                    if geometry["probe_max_mm"] <= .1:
                        report.update(proposal_embedding_and_probe_passed=True, selected_file=path.name)
                        break
                # 全量计数超过定位列表上限时拒绝本次局部定位，不拿截断对数作证书。
                pairs = checks.get("intersection_face_ids", [])
                if len(pairs) != checks["self_intersection_pairs"]:
                    report["reason"] = "intersection_location_list_not_complete"
                    break
                for a, b in pairs:
                    affected.update(int(v) for v in candidate.faces[[a, b]].reshape(-1))
            if report.get("proposal_embedding_and_probe_passed") or not legal:
                break
            _, working, selected = min(legal, key=lambda item: item[0])
            report["last_legal_file"] = selected
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
