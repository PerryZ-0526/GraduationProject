"""在已保存五个阻断输入上冻结比较两种独立碎片修复，不串联追加预算。"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from locality_diagnostic import digest, mesh_pair_drift, source_region, verify_labels
from locality_masks import save_obj_fp64
from locality_retriangulate import repair_degenerate
from locality_sliver_collapse import collapse_degenerate
from preflight_geogram_prefixes import metrics


def main():
    results = HERE / "实验结果"
    batch = results / "20261004_局部维护六路线C1开发_清理与复用"
    execution = json.loads((batch / "01-局部C1逐帧执行与独立审计.json").read_text(encoding="utf-8"))
    frozen = results / "20260928_后续输入冻结_v3"
    manifest = json.loads((frozen / "01-冻结清单.json").read_text(encoding="utf-8"))
    output = results / "20261004_退化碎片机制诊断"
    if output.exists():
        raise FileExistsError(output)
    output.mkdir()
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "scope": "五个已见拒绝输入，CPU定向开发；两种方法各自从相同输入开始，无新GPU或连续发布",
              "code_sha256": {name: digest(HERE / name) for name in
                  ("locality_retriangulate.py", "locality_sliver_collapse.py", "audit_locality_repairs.py")}, "rows": []}
    for row in execution["rows"]:
        if row["status"] != "retained_parent_and_stopped":
            continue
        name = row["route"] + "_" + row["event"]
        folder = batch / name
        source_path = folder / "source_clean.obj"
        if digest(source_path) != row["control"]["source_sha256"]:
            raise ValueError("原阻断输入改变")
        source = trimesh.load(source_path, force="mesh", process=False)
        bits = np.array(json.loads((folder / "labels_clean.json").read_text())["operand_bits"])
        parent = trimesh.load(row["published_state"]["mesh"], force="mesh", process=False)
        route = next(r for r in manifest["routes"] if r["id"] == row["route"])
        tool = trimesh.load(frozen / next(t["mesh"] for t in route["prefix_tools"] if t["event_id"] == row["event"]),
                            force="mesh", process=False)
        for method, repair in (("same_source_flip", repair_degenerate), ("plane_constrained_collapse", collapse_degenerate)):
            candidate, labels, operations = repair(source, bits)
            target = output / (name + "_" + method + ".obj")
            save_obj_fp64(candidate, target)
            reloaded = trimesh.load(target, force="mesh", process=False)
            checks = metrics(reloaded)
            _, _, seam = source_region(reloaded, labels)
            source_check = verify_labels(reloaded, labels, parent, tool, seam)
            accepted = bool(checks["finite"] and checks["watertight"] and checks["winding_consistent"] and
                checks["vertex_manifold_closed"] and checks["euler_number"] == 2 and checks["zero_area_faces"] == 0 and
                checks["fp32_zero_area_faces"] == 0 and checks["self_intersection_faces"] == 0 and
                source_check["passed_1e_8_mm_numerical_check"])
            report["rows"].append({"case": name, "method": method, "source_sha256": digest(source_path),
                "candidate_sha256": digest(target), "labels": labels.tolist(), "operations": operations,
                "checks": checks, "source_validation": source_check, "sampled_pair_drift": mesh_pair_drift(source, reloaded),
                "legal_pamo_input_under_listed_checks": accepted, "continuous_geometry_certified": False})
            (output / "01-退化碎片修复独立诊断.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(name, method, accepted, checks["zero_area_faces"], flush=True)
    report["status"] = "completed"
    (output / "01-退化碎片修复独立诊断.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
