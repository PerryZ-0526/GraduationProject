"""用已保存开发网格重审发布控制；这是离线C0检查，不是新局部C1序列。"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import numpy as np
import trimesh

from audit_followup_candidate import vertex_manifold_closed
from audit_pamo_outputs import audit_one
from locality_feedback import digest, maintain_frame
from locality_masks import external_contract, make_masks

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "实验结果"


def main():
    output = RESULTS / "20261004_局部维护发布控制复核"
    output.mkdir(exist_ok=True)
    record_path = output / "01-保存帧发布控制独立复核.json"
    if record_path.exists():
        raise FileExistsError(record_path)
    batch = RESULTS / "20261004_局部维护八轮折叠开发"
    ablations = RESULTS / "20261004_局部维护消融有效数字复核"
    manifest = json.loads((batch / "01-保存帧开发批次.json").read_text(encoding="utf-8"))
    c1 = json.loads((RESULTS / "20260929_C1试运行准备/01-C1试运行清单.json").read_text(encoding="utf-8"))
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "scope": "保存帧C0发布控制复核，不能替代新局部C1父网格反馈",
              "code_sha256": {name: digest(HERE / name) for name in
                              ("locality_feedback.py", "replay_locality_feedback.py", "locality_masks.py")},
              "rows": []}
    parents = {}
    for route in c1["routes"]:
        parent = RESULTS / "20260928_后续输入冻结_v3" / route["initial_mesh"]
        kind = "crossing" if route["category"] == "crossing" else "stop_resume"
        for index, event in enumerate(route["cutting_prefix_ids"]):
            parents[kind + "_" + event] = (parent, index)
            parent = RESULTS / "20260929_C1试运行准备/取回输出" / (kind + "_" + event) / "pamo.obj"
    for case in manifest["cases"]:
        name = case["case"]
        inputs = batch / name
        for filename, expected in case["files_sha256"].items():
            if digest(inputs / filename) != expected:
                raise ValueError("输入摘要不匹配：" + name)
        source = trimesh.load(inputs / "source.obj", force="mesh", process=False)
        tool = trimesh.load(inputs / "tool.obj", force="mesh", process=False)
        bits = json.loads((inputs / "labels.json").read_text())["operand_bits"]
        parent_path, version = parents[name]
        parent = {"mesh": str(parent_path), "sha256": digest(parent_path), "version": version}
        reference = RESULTS / "20260928_开发解析参照" / case["reference"]["mesh"]
        if digest(reference) != case["reference"]["sha256"]:
            raise ValueError("独立参照摘要不匹配")

        def build(source_path, method, rings):
            if method == "boolean" and rings == 0:
                folder = ablations / "取回输出/ablation_fp64_outputs" / name
                stem = "r0_boolean_no_transition"
            else:
                folder = batch / "取回输出/eight_pass_outputs" / name
                stem = "r0_" + method
            target = folder / (stem + ".obj")
            execution = json.loads((folder / (stem + ".json")).read_text())
            if digest(target) != execution["output_sha256"]:
                raise ValueError("候选摘要不匹配")
            return target

        def audit(target, method, rings):
            mesh = trimesh.load(target, force="mesh", process=False)
            metrics = audit_one(inputs / "source.obj", target, reference)
            log = target.with_suffix(".log").read_text(encoding="utf-8")
            evidence = {"topology_passed": bool(metrics["topology_passed"]),
                        "sampled_geometry_passed": bool(metrics["sampled_geometry_passed"]),
                        "vertex_manifold": bool(vertex_manifold_closed(mesh.faces)),
                        "finite_nondegenerate": bool(np.isfinite(mesh.vertices).all() and
                                                       np.all(mesh.area_faces > 1e-12)),
                        "capacity_unchanged": not ("exceeds max_blocks" in log or "Number of contacts" in log),
                        "metrics": metrics}
            if method == "boolean":
                active, fixed = make_masks(source, bits, tool, "boolean", rings=rings)
                ids = np.load(target.with_name(target.stem + "_original_ids.npy"))
                contract = external_contract(source, mesh, ids, active, fixed)
                evidence.update(fixed_contract_passed=contract["passed"], fixed_contract=contract)
            return evidence

        state, details = maintain_frame(parent, inputs / "source.obj", build, audit, case["input_valid"])
        report["rows"].append({"case": name, "input_valid": case["input_valid"],
                               "state": state, **details})
        record_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(name, details["published"], len(details["attempts"]), flush=True)
    report["status"] = "completed"
    record_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
