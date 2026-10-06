"""按完整计划核对证据覆盖，区分实验记录完整与算法成功。"""

import argparse
import json
from pathlib import Path

from audit_followup_candidate import sha256
from run_geometry_study import save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ledger_path = args.output / "01-全范围冻结与执行账本.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    requirements = []
    def check(name, passed, evidence, limitation=""):
        requirements.append({"requirement": name, "evidence_complete": bool(passed),
                             "evidence": evidence, "limitation": limitation})
    check("冻结方法无事后修改", all(sha256(here / name) == expected
        for name, expected in ledger["code_sha256"].items()), str(ledger_path))
    frozen_inputs = [(r["initial_mesh"], r["initial_mesh_sha256"]) for r in manifest["routes"]]
    frozen_inputs += [(t["mesh"], t["sha256"]) for r in manifest["routes"] for t in r["prefix_tools"]]
    frozen_inputs += [(f["mesh"], f["sha256"]) for f in manifest["negative_inputs"]]
    check("全部初态工具及小特征输入摘要一致", ledger["input_manifest_sha256"] == sha256(manifest_path)
        and all(sha256(args.prepared / "inputs" / name) == expected for name, expected in frozen_inputs), str(manifest_path))
    for split, expected_routes, expected_events in (("long", 2, 48), ("application", 2, 154), ("evaluation", 12, 48)):
        routes = [r for r in manifest["routes"] if r["split"] == split]
        path = args.output / split / "01-反馈执行与独立审计.json"
        audit_path = args.output / split / "03-反馈完整分母与父链复核.json"
        complete = len(routes) == expected_routes and sum(len(r["cutting_prefix_ids"]) for r in routes) == expected_events
        if path.exists() and audit_path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            complete &= record["status"] == "completed_with_recorded_failures" and audit["audit_passed"]
            complete &= audit["record_sha256"] == sha256(path)
            for row in record["rows"]:
                if row["status"] == "contained_reused_parent":
                    # 复用事件没有新候选目录，摘要必须等于已核对父快照。
                    complete &= row["output_sha256"] == row["parent_sha256"]
                elif row.get("output_sha256"):
                    candidate = args.output / split / (row["route"] + "_" + row["event"] + "_" + row["branch"]
                        + "_" + row["selected_method"]) / "candidate.obj"
                    complete &= candidate.exists() and sha256(candidate) == row["output_sha256"]
        else:
            complete = False
        check(split + "完整分母、父链及候选摘要", complete, str(path), "阻断前缀仅记失败，不代表全部几何帧生成成功")
    path = args.output / "features" / "02-浅磨特征保持审计.json"
    complete = False
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
        complete = record["status"] == "completed_with_recorded_failures" and len(manifest["negative_inputs"]) == 9
        for feature in manifest["negative_inputs"]:
            rows = [r for r in record["rows"] if r["case"] == feature["id"]]
            # 布尔全局失败可一次记录阻断全部方法；不得凭空添加GPU执行次数。
            complete &= (len(rows) == 1 and rows[0]["status"] == "geogram_failed") or (
                len(rows) == 3 and {r["method"] for r in rows} == {"full", "spatial", "boolean"})
            for row in rows:
                if row.get("output_sha256"):
                    output = args.output / "features" / (feature["id"] + "_" + row["method"]) / "candidate.obj"
                    complete &= output.exists() and sha256(output) == row["output_sha256"]
    check("九个新小特征三方法对照覆盖", complete, str(path), "预期拓扑来自同次浅磨CSG；有限抽样非连续证书")
    check("完整执行账本终态", ledger["status"] == "all_stages_finished_requires_completion_audit", str(ledger_path))
    result = {"time_beijing": now(), "requirements": requirements,
        "frozen_validation_evidence_complete": all(r["evidence_complete"] for r in requirements),
        "scope": "仅本批冻结验证证据覆盖；尚须开发消融、独立网格重审、科学结论及文档核对，不自动完成目标",
        "algorithm_success": "需由质量—误差—连续性结果判断；此检查不认证算法优势或连续几何"}
    save(args.output / "05-完整冻结验证证据覆盖核对.json", result)
    print(json.dumps({"complete": result["frozen_validation_evidence_complete"],
        "missing": [r["requirement"] for r in requirements if not r["evidence_complete"]]}, ensure_ascii=False))
    if not result["frozen_validation_evidence_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
