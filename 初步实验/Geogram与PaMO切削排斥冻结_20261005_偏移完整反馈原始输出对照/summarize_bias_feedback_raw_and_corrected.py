"""核对两档完整父反馈，同输入原始GPU与排斥维护输出分别统计。"""

import argparse
import json
from pathlib import Path
import sys

# 固定数值依赖，不能随共享开发目录的后续修改改变观察结果。
SNAPSHOT = Path(__file__).parents[1] / "Geogram与PaMO切削排斥冻结_20261005_误差分布观察"
sys.path.insert(0, str(SNAPSHOT))
from audit_followup_candidate import sha256, quality_distribution
from audit_cut_delivery import probes
from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution
from run_geometry_study import save, now
import trimesh


def load_json(path):
    return json.loads(path.read_text("utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--zero-batch", type=Path, required=True)
    parser.add_argument("--zero-audit", type=Path, required=True)
    parser.add_argument("--original-batch", type=Path, required=True)
    parser.add_argument("--original-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # 先核对全部冻结依赖，再读取两套终态，任何分母或对象绑定错误均停止。
    dependency_manifest = SNAPSHOT / "01-执行源码冻结清单.json"
    for item in load_json(dependency_manifest):
        if sha256(SNAPSHOT / item["file"]) != item["sha256"]:
            raise ValueError("冻结数值依赖摘要改变")
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = load_json(manifest_path)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，八个实际同输入原GPU与维护输出对照",
              "文档概述": "两套完整反馈及保存复审先核对，再统计原GPU与维护分布；有限侵入见证不是体积或连续证书",
              "索引目录": ["evidence", "rows", "summary"], "status": "running", "rows": [], "evidence": [],
              "dependency_manifest_sha256": sha256(dependency_manifest), "script_sha256": sha256(Path(__file__))}
    bound_route = None
    first_inputs = []
    args.output.mkdir(exist_ok=False)
    record = args.output / "01-偏移完整反馈原始GPU与排斥维护对照.json"
    for factor, batch_root, audit_root in [(0.0, args.zero_batch, args.zero_audit),
                                           (0.9, args.original_batch, args.original_audit)]:
        batch_path = batch_root / "01-统一配置完整父反馈记录.json"
        audit_path = audit_root / "01-保存候选整面与材料侧独立复审.json"
        batch, audit = load_json(batch_path), load_json(audit_path)
        route = next(r for r in manifest["routes"] if r["id"] == batch["selected_route"])
        if bound_route is not None and route["id"] != bound_route:
            raise ValueError("两档不是同一冻结路线")
        bound_route = route["id"]
        events = route["cutting_prefix_ids"]
        if (batch["status"] != "completed_with_recorded_outcomes" or
                batch["summary"] != {"published": 4, "events": 4, "whole_route_complete": True} or
                audit["status"] != "completed" or len(audit["rows"]) != 4 or len(events) != 4 or
                audit["source_batch_sha256"] != sha256(batch_path) or
                batch["manifest_sha256"] != sha256(manifest_path) or
                batch["protocol"]["stage1_SDF_offset_factor"] != factor or
                [r["event"] for r in batch["rows"]] != events):
            raise ValueError("完整四刀终态、保存复审或偏移协议不匹配")
        report["evidence"].append({"factor": factor, "batch_sha256": sha256(batch_path), "audit_sha256": sha256(audit_path)})
        parent = route["initial_mesh_sha256"]
        for index, row in enumerate(batch["rows"]):
            event = row["event"]
            certified = [r for r in audit["rows"] if r["route"] == bound_route and r["event"] == event]
            if len(certified) != 1 or not certified[0]["passed"] or row["parent_sha256"] != parent:
                raise ValueError("实际保存复审或父链不匹配")
            folder = batch_root / f"{bound_route}_{event}_candidate_boolean"
            input_folder = batch_root / f"{bound_route}_{event}_candidate_input"
            raw, final = folder / "raw_full_candidate.obj", folder / "candidate.obj"
            source_path, labels_path = input_folder / "clean_source.obj", input_folder / "clean_labels.json"
            reference_path = batch_root / f"{bound_route}_{event}_reference" / "validated_reference.obj"
            if not reference_path.exists():
                reference_path = reference_path.with_name("reference.obj")
            expected = row["attempt"]
            if (sha256(raw) != expected["raw_full_output_sha256"] or sha256(final) != row["output_sha256"] or
                    sha256(source_path) != expected["inputs_sha256"]["source.obj"] or
                    sha256(labels_path) != expected["inputs_sha256"]["labels.json"] or
                    sha256(reference_path) != row["reference_sha256"]):
                raise ValueError("原GPU、维护源、标签、参照或最终保存对象摘要错误")
            parent = row["output_sha256"]
            prefix = set(events[:index + 1])
            tool_items = [t for t in route["prefix_tools"] if t["event_id"] in prefix]
            tool_paths = [args.prepared / "inputs" / t["mesh"] for t in tool_items]
            if [sha256(p) for p in tool_paths] != [t["sha256"] for t in tool_items]:
                raise ValueError("累计工具摘要错误")
            tools = [trimesh.load(p, force="mesh", process=False) for p in tool_paths]
            source = trimesh.load(source_path, force="mesh", process=False)
            reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
            bits = load_json(labels_path)["operand_bits"]
            entry = {"offset_factor": factor, "event": event, "parent_sha256": row["parent_sha256"],
                     "input_sha256": expected["inputs_sha256"], "reference_sha256": sha256(reference_path),
                     "saved_reaudit_passed": True, "objects": {}}
            for name, path in [("raw_GPU", raw), ("corrected_saved", final)]:
                mesh = trimesh.load(path, force="mesh", process=False)
                entry["objects"][name] = {"sha256": sha256(path), "quality": quality_distribution(mesh),
                    "cumulative_distribution": geometry_error_distribution(mesh, reference),
                    "cutting_surface_distribution": cutting_surface_distribution(mesh, source, bits),
                    "finite_intrusion_witnesses": probes(mesh, tools)}
            if index == 0:
                first_inputs.append(expected["inputs_sha256"])
            report["rows"].append(entry)
            save(record, report)
            print(factor, event, "raw_and_corrected_saved", flush=True)
    # 首刀输入须严格相同；后续两档的真实父链允许分歧，不能假称全部同源消融。
    if first_inputs[0] != first_inputs[1]:
        raise ValueError("两档首刀实际GPU输入不同")
    report.update(status="completed", finished_beijing=now(), summary={"events": 8, "stored_objects": 16,
        "within_event_GPU_input_shared": True, "between_offsets_first_input_identical": True,
        "later_parents_may_differ": True, "new_GPU_calls": 0, "fixed_geometry_gate": None,
        "continuous_geometry_certified": False})
    save(record, report)


if __name__ == "__main__":
    main()
