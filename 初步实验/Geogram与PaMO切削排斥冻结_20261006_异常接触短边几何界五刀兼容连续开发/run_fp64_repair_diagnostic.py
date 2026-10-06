"""隔离检查物理面积修复与编码退化修复是否混用，不执行GPU或发布。"""
import argparse
from pathlib import Path
import json
import numpy as np
import trimesh
from physical_repair_operations import SOURCES, OPERATIONS
from opposed_facet_cleanup import clean_cancel_opposed
from preserved_feedback_gate import local_fp64_valid
from preserved_input_repair import repair_preserved_input
from locality_masks import save_obj_fp64
from run_constrained_feedback import global_geometry
from run_geometry_study import now, save
from audit_followup_candidate import sha256


def physical_operations(folder):
    # 诊断和反馈使用同一私有操作；保存实际副本供复核，原修复源码不变。
    for name, source in SOURCES.items():
        (folder/name).write_text(source, encoding="utf-8")
    return OPERATIONS


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    raw = trimesh.load(args.source, process=False)
    bits = json.loads(args.labels.read_text(encoding="utf-8"))["operand_bits"] if args.labels else np.ones(len(raw.faces), int)
    clean, bits, cleanup = clean_cancel_opposed(raw, bits, allow_shared=True)
    old, _, old_record = repair_preserved_input(clean, bits)
    ops = physical_operations(args.output)
    candidate, labels, steps = clean.copy(), np.asarray(bits).copy(), []
    for name in ("repair_degenerate", "collapse_degenerate", "repair_degenerate"):
        options = dict(allow_shared=True)
        if name == "collapse_degenerate":
            options["allow_small_incident"] = True
        candidate, labels, details = ops[name](candidate, labels, **options)
        steps.append(dict(operation=name, details=details))
        if not ops["invalid_faces"](candidate.vertices, candidate.faces).any():
            break
    save_obj_fp64(candidate, args.output/"candidate.obj")
    save(args.output/"labels.json", dict(operand_bits=labels.tolist()))
    # 只报告本地候选，不用报警复核或抽样结果冒充全量精确嵌入和发布。
    valid, metrics = local_fp64_valid(candidate)
    geometry = global_geometry(clean, candidate)
    result = dict(time_beijing=now(), source_sha256=sha256(args.source),
        cleanup=cleanup, original_repair=old_record, physical_steps=steps,
        metrics=metrics, geometry=geometry, candidate_sha256=sha256(args.output/"candidate.obj"),
        local_physical_candidate=bool(valid and geometry["probe_max_mm"] <= 1e-7),
        requires_full_exact_embedding=True, published=False, continuous_geometry_certified=False)
    save(args.output/"01-物理面积判据隔离诊断.json", result)
    print(result["local_physical_candidate"], metrics["zero_area_faces"], metrics["fp32_zero_area_faces"], geometry["probe_max_mm"])
