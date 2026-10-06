"""统计三档偏移的六张实际原GPU输出，不作合法性接受或连续反馈结论。"""

import argparse
import json
from pathlib import Path

import trimesh
import run_reference_cut_feedback
from audit_followup_candidate import sha256, quality_distribution
from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution
from run_geometry_study import now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--probes", type=Path, nargs=3, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    batch_path = args.previous / "01-统一配置完整父反馈记录.json"
    batch = json.loads(batch_path.read_text("utf8"))
    event = next(row for row in batch["rows"] if row["event"] == "e1")
    stem = batch["selected_route"] + "_e1"
    source = args.previous / (stem + "_candidate_input") / "clean_source.obj"
    labels = source.with_name("clean_labels.json")
    reference_path = args.previous / (stem + "_reference") / "validated_reference.obj"
    if not reference_path.exists():
        reference_path = reference_path.with_name("reference.obj")
    for path, digest in ((source, event["attempt"]["inputs_sha256"]["source.obj"]),
                         (labels, event["attempt"]["inputs_sha256"]["labels.json"]),
                         (reference_path, event["reference_sha256"])):
        if sha256(path) != digest:
            raise ValueError("实际源、标签或累计独立参照摘要改变")
    maintenance = trimesh.load(source, force="mesh", process=False)
    reference = trimesh.load(reference_path, force="mesh", process=True)
    bits = json.loads(labels.read_text("utf8"))["operand_bits"]
    args.output.mkdir(exist_ok=False)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，六张原GPU输出独立分布统计",
              "文档概述": "原GPU尚未经过排斥维护，统计不等于最终质量接受，不算连续或未见评价",
              "索引目录": ["rows"], "batch_sha256": sha256(batch_path), "new_GPU_calls": 0, "rows": []}
    for root in args.probes:
        path = root / "01-简化邻接顺序同输入完整对照.json"
        probe = json.loads(path.read_text("utf8"))
        if probe["status"] != "completed" or probe["previous_record_sha256"] != sha256(batch_path) or probe["selected_event"] != "e1":
            raise ValueError("要求同一事件完整GPU记录")
        for index, gpu in enumerate(probe["rows"], 1):
            candidate_path = root / f"同输入GPU第{index}次" / "candidate.obj"
            if gpu["execution"]["returncode"] or sha256(candidate_path) != gpu["output_sha256"]:
                raise ValueError("实际GPU输出无效或改变")
            candidate = trimesh.load(candidate_path, force="mesh", process=False)
            # 原输出分布单独保存，不能以较小误差绕过后续全网格合法性门控。
            row = {"offset_factor": probe["offset_factor"], "repeat": index, "saved_sha256": sha256(candidate_path),
                   "probe_record_sha256": sha256(path), "cumulative_distribution": geometry_error_distribution(candidate, reference),
                   "source_distribution": geometry_error_distribution(candidate, maintenance),
                   "cutting_surface_distribution": cutting_surface_distribution(candidate, maintenance, bits),
                   "quality": quality_distribution(candidate)}
            report["rows"].append(row)
            print(row["offset_factor"], index, row["cumulative_distribution"]["minimum_bidirectional_area_fraction_within_0_1_mm"], flush=True)
    if len(report["rows"]) != 6 or sorted(row["offset_factor"] for row in report["rows"]) != [0.0, 0.0, 0.45, 0.45, 0.9, 0.9]:
        raise ValueError("三档六输出分母不完整")
    save(args.output / "01-三档偏移六张原GPU分布与质量.json", report)


if __name__ == "__main__":
    main()
