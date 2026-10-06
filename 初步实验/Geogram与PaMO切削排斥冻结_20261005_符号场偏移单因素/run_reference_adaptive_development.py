"""复用已保存GPU原始对象，冻结参照自适应候选并独立审计公开八骨首刀。"""

import argparse
import getpass
import json
from pathlib import Path
from time import perf_counter

import trimesh

from audit_followup_candidate import sha256, quality_distribution
from audit_cut_delivery import probes
from cut_side_classifier import ExactCutSide
from reference_adaptive_exclusion import reference_adaptive_exclusion
from locality_masks import save_obj_fp64
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import execute, save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validation = json.loads((args.side_validation / "01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))
    if validation["status"] != "completed" or not all(x["passed"] for x in validation["tests"]):
        raise ValueError("精确侧分类器未通过控制验证")
    args.output.mkdir(exist_ok=False)
    config = dict(line.split("=", 1) for line in (HERE.parents[1] / ".env").read_text("utf8").splitlines()
                  if line and not line.startswith("#"))
    original = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(args.output, int(config["CUDA_SSH_PORT"]))
    finally:
        getpass.getpass = original
        del config
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，先冻结再打开开发候选输出",
              "文档概述": "八已见骨首刀开发，不称独立评价；不新增相同GPU调用",
              "索引目录": ["protocol", "rows"], "status": "running", "rows": [],
              "snapshot_sha256": sha256(HERE / "01-执行源码冻结清单.json"),
              "protocol": {"max_levels": 4, "correction_seed_budget_mm": .1, "target_geometry_probe_budget_mm": .1,
                  "geometry_trigger_mm": .025, "anchor": "full_EPECK_embedding_then_exact_material_side",
                  "new_GPU_calls": 0, "raw_GPU_restore_displacement_limited": False}}
    record = args.output / "01-参照自适应排斥开发与审计.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("开发审计目录已存在")
        executable = validation["environment"]["executable"]
        if execute(engine.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("已验证精确分类器已改变")
        side = ExactCutSide(engine, executable)
        save(record, report)
        manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
        for route in manifest["routes"]:
            rid = route["id"]
            raw_path = args.batch / f"{rid}_e0_full_full/raw_for_equal_input_reuse.obj"
            reference_folder = args.batch / f"{rid}_e0_reference"
            reference_path = reference_folder / "validated_reference.obj"
            if not reference_path.exists():
                reference_path = reference_folder / "reference.obj"
            tool_path = args.prepared / "inputs" / route["prefix_tools"][0]["mesh"]
            raw = trimesh.load(raw_path, force="mesh", process=False)
            reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
            tool = trimesh.load(tool_path, force="mesh", process=False)
            start = perf_counter()
            mesh, details = reference_adaptive_exclusion(raw, [tool], reference, side.anchor)
            path = args.output / f"{rid}_candidate.obj"
            save_obj_fp64(mesh, path)
            row = {"route": rid, "raw_sha256": sha256(raw_path), "reference_sha256": sha256(reference_path),
                "tool_sha256": sha256(tool_path), "saved_sha256": sha256(path), "details": details,
                "total_CPU_and_remote_audit_ms": (perf_counter() - start) * 1000,
                "quality": quality_distribution(mesh), "probes": probes(mesh, [tool])}
            report["rows"].append(row)
            save(record, report)
            print(rid, "accepted", details["accepted"], "levels", len(details["attempts"]), flush=True)
        report.update(status="completed_development", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
