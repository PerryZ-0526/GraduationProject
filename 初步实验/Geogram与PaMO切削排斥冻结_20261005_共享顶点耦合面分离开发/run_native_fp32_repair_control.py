"""固定已拒绝第三刀源，核对原生FP32检测触发后的既有碎片修复。"""

import argparse
import json
from pathlib import Path

import trimesh

from run_reference_cut_feedback import ReferenceCutEngine
from native_fp32_fragment_guard import repair_input_native_fp32
from input_full_embedding_audit import audit_input_with_full_embedding
from locality_masks import save_obj_fp64
from locality_diagnostic import source_region, verify_labels
from audit_followup_candidate import sha256
from run_geometry_study import execute, save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    old_path = args.previous / "01-统一配置完整父反馈记录.json"
    old = json.loads(old_path.read_text("utf8"))
    row = next(x for x in old["rows"] if x["event"] == "e2")
    if old["status"] == "running" or row["status"] != "maintenance_input_rejected":
        raise ValueError("必须固定已终态输入拒绝")
    rid = old["selected_route"]
    source_path = args.previous / f"{rid}_e2_candidate_input/clean_source.obj"
    parent_path = args.previous / f"{rid}_e1_candidate_boolean/candidate.obj"
    if sha256(parent_path) != row["parent_sha256"]:
        raise ValueError("实际父状态已变化")
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，先固定真实失败源及父状态",
              "文档概述": "只检验第三刀输入修复，不声称连续完成", "索引目录": ["repair", "provenance"],
              "status": "running", "parent_sha256": sha256(parent_path), "source_sha256": sha256(source_path),
              "previous_record_sha256": sha256(old_path), "guard_sha256": sha256(Path(__file__).with_name("native_fp32_fragment_guard.py"))}
    record = args.output / "01-修复后输入全量门控同源对照.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("隔离审计目录已存在")
        source = trimesh.load(source_path, force="mesh", process=False)
        labels = json.loads(source_path.with_name("clean_labels.json").read_text("utf8"))["operand_bits"]
        tool_info = next(t for t in engine.routes[rid]["prefix_tools"] if t["event_id"] == "e2")
        tool_path = args.prepared / "inputs" / tool_info["mesh"]
        if sha256(tool_path) != row["tool_sha256"]:
            raise ValueError("冻结工具已变化")
        check = lambda mesh: audit_input_with_full_embedding(engine, args.output, mesh, report)
        candidate, bits, report["repair"] = repair_input_native_fp32(source, labels, audit=check,
                                                   allow_shared=True, allow_small_incident=True)
        _, _, seam = source_region(candidate, bits, allow_shared=True)
        report["provenance"] = verify_labels(candidate, bits, trimesh.load(parent_path, force="mesh", process=False),
            trimesh.load(tool_path, force="mesh", process=False), seam, allow_shared=True)
        output = args.output / "clean_source.obj"
        save_obj_fp64(candidate, output)
        save(args.output / "clean_labels.json", {"operand_bits": bits.tolist()})
        report.update(status="completed", finished_beijing=now(), repaired_sha256=sha256(output),
            labels_sha256=sha256(args.output / "clean_labels.json"), tool_sha256=sha256(tool_path),
            accepted=bool(report["repair"]["accepted"] and report["provenance"]["passed_1e_8_mm_numerical_check"]))
        save(record, report)
        print("native_FP32_same_source_repair", report["accepted"], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
