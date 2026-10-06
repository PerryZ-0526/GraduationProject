"""对公开骨面首个失败顶点区分半空间不可行、预算不足和数值求解拒绝。"""

import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import LinearConstraint, linprog, minimize, nnls
import trimesh

# 使用原试验冻结依赖，不重新选择面支撑或扩大原验收预算。
SNAPSHOT = Path(__file__).parents[1] / "Geogram与PaMO切削排斥冻结_20261004_保留配对"
sys.path.insert(0, str(SNAPSHOT))
from cut_exclusion import supporting_planes
from audit_followup_candidate import sha256
from run_geometry_study import save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    args = parser.parse_args()
    path = args.pilot / "01-参照恢复与整面排斥开发消融.json"
    pilot = json.loads(path.read_text("utf8"))
    manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
    routes = {r["id"]: r for r in manifest["routes"]}
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，冻结首个失败顶点可行性诊断",
              "文档概述": "浮点最小距离只作诊断；非负半空间组合用有理数核对信赖球不可行证据",
              "索引目录": ["rows"], "pilot_sha256": sha256(path),
              "script_sha256": sha256(Path(__file__)),
              "snapshot_sha256": sha256(SNAPSHOT / "01-执行源码冻结清单.json"), "rows": []}
    (args.pilot / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    for row in pilot["rows"]:
        details = row["exclusion"]["attempts"][0]["exclusion"]
        vertex = details.get("failed_vertex")
        if vertex is None:
            continue
        mesh = trimesh.load(args.pilot / f"{row['route']}_restore_only.obj", force="mesh", process=False)
        tool_path = args.prepared / "inputs" / routes[row["route"]]["prefix_tools"][0]["mesh"]
        tool = trimesh.load(tool_path, force="mesh", process=False)
        normals, offsets = supporting_planes(tool)
        selected = np.asarray(details["frozen_face_support_ids"])
        owners = np.flatnonzero(np.any(mesh.faces == vertex, axis=1))
        planes = np.unique(selected[:, owners])
        matrix = normals[planes]
        center = mesh.vertices[vertex]
        bounds = offsets[planes] + 1e-8 - matrix @ center
        lp = linprog(np.zeros(3), A_ub=-matrix, b_ub=-bounds, bounds=[(None, None)] * 3, method="highs")
        entry = {"route": row["route"], "vertex": vertex, "planes": planes.tolist(),
                 "seed_sha256": sha256(args.pilot / f"{row['route']}_restore_only.obj"),
                 "tool_sha256": sha256(tool_path),
                 "LP_status": int(lp.status), "LP_message": lp.message,
                 "exact_feasible_within_original_seed_budget": False}
        if lp.success:
            # 从LP可行点求最近可行点，避免零初值和非线性信赖球干扰可行性诊断。
            result = minimize(lambda x: .5 * float(x @ x), lp.x, jac=lambda x: x,
                              constraints=[LinearConstraint(matrix, bounds, np.inf)], method="SLSQP",
                              options={"ftol": 1e-15, "maxiter": 300})
            point = center + result.x
            exact_point = tuple(Fraction(float(x)) for x in point)
            support = all(sum(Fraction(float(a)) * b for a, b in zip(n, exact_point)) >= Fraction(float(offset))
                          for n, offset in zip(matrix, offsets[planes]))
            displacement = sum((a - Fraction(float(b))) ** 2 for a, b in zip(exact_point, center))
            entry.update(solver_success=bool(result.success), solver_message=result.message,
                         closest_displacement_mm=float(np.linalg.norm(result.x)),
                         numerical_constraint_violation=float(np.max(bounds - matrix @ result.x)),
                         exact_face_support_point_passed=support,
                         exact_feasible_within_original_seed_budget=bool(support and displacement <= Fraction(".1") ** 2))
            # 任意非负权重组合都给出必要半空间；柯西不等式可精确证明整个0.1毫米球不可行。
            weights, _ = nnls(matrix.T, result.x)
            coefficients = [Fraction(float(x)) for x in weights]
            exact_center = tuple(Fraction(float(x)) for x in center)
            combined = [sum(w * Fraction(float(n[axis])) for w, n in zip(coefficients, matrix)) for axis in range(3)]
            right = sum(w * (Fraction(float(offset)) - sum(Fraction(float(a)) * b for a, b in zip(n, exact_center)))
                        for w, n, offset in zip(coefficients, matrix, offsets[planes]))
            square = sum(x * x for x in combined)
            infeasible = bool(all(w >= 0 for w in coefficients) and right > 0
                              and right * right > Fraction(".1") ** 2 * square)
            entry["exact_budget_infeasibility_certificate"] = {
                "passed": infeasible, "nonnegative_weights_fp64": weights.tolist(),
                "combined_right_exact": str(right), "combined_normal_squared_exact": str(square),
                "lower_distance_mm": float(right) / float(square) ** .5 if square > 0 else None,
                "scope": "固定当前面支撑下的单顶点0.1毫米球无解；不证明其他支撑或连接无解"}
        report["rows"].append(entry)
        print(row["route"], entry["LP_status"], entry.get("closest_displacement_mm"),
              entry["exact_feasible_within_original_seed_budget"], flush=True)
    save(args.pilot / "02-冻结失败顶点半空间可行性诊断.json", report)


if __name__ == "__main__":
    main()
