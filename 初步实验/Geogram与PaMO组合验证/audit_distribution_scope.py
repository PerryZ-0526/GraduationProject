"""同版八骨32事件的观察反馈证据核对，运行前缀与终态分别计数。"""

import argparse
import json
from pathlib import Path

from audit_followup_candidate import sha256
from run_geometry_study import now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared", "single", "single-audit", "remaining", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text("utf8"))
    args.output.mkdir(exist_ok=True)
    rows, hashes = [], set()
    for route in manifest["routes"]:
        rid = route["id"]
        folder = args.single if rid == "BP3D_FJ3368_交叉浅磨" else args.remaining / rid
        entry = {"route": rid, "planned_events": len(route["cutting_prefix_ids"]), "status": "not_started", "observed": 0, "reaudited": 0}
        rows.append(entry)
        path = folder / "01-统一配置完整父反馈记录.json"
        if not path.exists():
            continue
        record = json.loads(path.read_text("utf8"))
        if record["manifest_sha256"] != sha256(manifest_path) or record["selected_route"] != rid:
            raise ValueError("路线或输入清单不同")
        hashes.add(tuple(sorted(record["environment"]["distribution_code_sha256"].items())))
        if record["protocol"].get("fixed_geometry_acceptance_threshold", "missing") is not None:
            raise ValueError("不是无固定几何门槛观察版")
        entry.update(status=record["status"], execution_path=str(path.resolve()), execution_sha256=sha256(path),
                     events=[{"event": row["event"], "status": row["status"]} for row in record["rows"]])
        parent = route["initial_mesh_sha256"]
        observed = []
        for row in record["rows"]:
            if row["status"] != "published_geometry_observation":
                continue
            stem = rid + "_" + row["event"]
            candidate = folder / (stem + "_candidate_boolean") / "candidate.obj"
            source = folder / (stem + "_candidate_input") / "clean_source.obj"
            labels = source.with_name("clean_labels.json")
            reference = folder / (stem + "_reference") / "validated_reference.obj"
            if not reference.exists():
                reference = reference.with_name("reference.obj")
            attempt = row["attempt"]
            matches = (row["parent_sha256"] == parent and sha256(candidate) == row["output_sha256"] == attempt["output_sha256"]
                       and sha256(source) == attempt["inputs_sha256"]["source.obj"]
                       and sha256(labels) == attempt["inputs_sha256"]["labels.json"]
                       and sha256(reference) == row["reference_sha256"] == attempt["cut_exclusion"]["cumulative_reference_sha256"])
            if not matches:
                raise ValueError("真实父链、候选、维护源、标签或参照摘要不同")
            if not attempt["cut_exclusion"]["accepted"] or not attempt["exact_embedding"].get("embedded_closed"):
                raise ValueError("观察发布没有合法性证据")
            parent = row["output_sha256"]
            observed.append(row)
        entry["observed"] = len(observed)
        entry["recorded_GPU_attempts"] = sum("attempt" in row for row in record["rows"])
        if record["status"] == "completed_with_recorded_outcomes":
            if [row["event"] for row in record["rows"]] != route["cutting_prefix_ids"]:
                raise ValueError("终态原事件分母缺失或乱序")
            if record["summary"]["published"] != len(observed):
                raise ValueError("观察发布计数不同")
            entry["complete_observation_route"] = len(observed) == len(route["cutting_prefix_ids"])
        audit_path = (args.single_audit if folder == args.single else args.remaining / (rid + "_保存复审")) / "01-保存候选整面与材料侧独立复审.json"
        if audit_path.exists():
            audit = json.loads(audit_path.read_text("utf8"))
            if audit["source_batch_sha256"] != sha256(path):
                raise ValueError("保存复审没有绑定当前终态")
            if audit["status"] == "completed":
                if [(row["route"], row["event"]) for row in audit["rows"]] != [(rid, row["event"]) for row in observed]:
                    raise ValueError("保存复审事件不一一对应实际观察发布")
                if any(not row["passed"] for row in audit["rows"]):
                    raise ValueError("保存复审覆盖不完整或失败")
                # 复审实际精确分类对象也必须逐张对应当前保存网格，不能只看成功总数。
                for saved, reviewed in zip(observed, audit["rows"]):
                    if any(anchor["classification"]["saved_mesh_sha256"] != saved["output_sha256"] for anchor in reviewed["anchors"]):
                        raise ValueError("精确分类对象与实际保存网格不同")
                entry["reaudited"] = len(audit["rows"])
                entry["audit_path"], entry["audit_sha256"] = str(audit_path.resolve()), sha256(audit_path)
    if len(hashes) != 1:
        raise ValueError("分布机制不止一个版本或没有实际版本证据")
    complete = all(row["status"] == "completed_with_recorded_outcomes" and row["reaudited"] == row["observed"] for row in rows)
    output_path = args.output / "01-同版八骨观察范围与证据核对.json"
    generated = json.loads(output_path.read_text("utf8"))["生成时间"] if output_path.exists() else now()
    report = {"生成时间": generated, "修改时间及修改内容": now() + "，核对当前实际保存证据，不把运行前缀当作完整终态",
              "文档概述": "原八骨32事件，同算法观察发布与最终几何质量结论分开",
              "索引目录": ["rows", "summary"], "status": "completed" if complete else "incomplete_verified_snapshot",
              "manifest_sha256": sha256(manifest_path), "fixed_geometry_acceptance_threshold": None,
              "geometry_quality_decision": "statistics_only_pending_evaluation", "rows": rows,
              "summary": {"routes": len(rows), "planned_events": sum(row["planned_events"] for row in rows),
                          "observed_including_live_prefix": sum(row["observed"] for row in rows),
                          "saved_reaudited": sum(row["reaudited"] for row in rows),
                          "recorded_GPU_attempts_including_inherited": sum(row.get("recorded_GPU_attempts", 0) for row in rows),
                          "complete_terminal_observation_routes": sum(row.get("complete_observation_route", False) for row in rows)}}
    save(output_path, report)
    print(report["status"], report["summary"], flush=True)


if __name__ == "__main__":
    main()
