"""共面区域候选的完整GPU阶段开发检查，不将并发负载耗时作加速证据。"""

import argparse
import json
from pathlib import Path
from run_planar_feedback import PlanarEngine
from run_adaptive_feedback import audit_adaptive
from run_constrained_batch import HERE
from run_geometry_study import save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tangent", action="store_true", help="使用新增点的切平面投影约束")
    parser.add_argument("--public", action="store_true", help="取两张已见公开肩胛骨首帧阻断输入")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.tangent:
        from run_tangent_feedback import TangentEngine
        engine = TangentEngine(args.output, args.port)
    else:
        engine = PlanarEngine(args.output, args.port)
    report = {"time_beijing": now(), "status": "running", "rows": [], "scope": "两张已见保存输入；GPU存在其他研究批次，不进行性能比较"}
    try:
        report["environment"] = engine.setup()
        prepared = HERE / "实验结果/20261004_局部维护保存帧开发"
        manifest = json.loads((prepared / "01-保存帧开发批次.json").read_text(encoding="utf-8"))
        fixtures = [(case["case"], prepared / case["case"] / "source.obj", prepared / case["case"] / "labels.json", prepared / case["case"] / "tool.obj") for case in manifest["cases"][:2]]
        if args.public:
            assets = HERE.parent / "可复用磨削测试集/公开浅磨批次_v2"
            public = json.loads((assets / "01-完整范围冻结清单.json").read_text(encoding="utf-8"))
            fixtures = []
            for route in public["routes"][:2]:
                inputs = HERE / "实验结果/20261004_共面候选公开骨面反馈" / (route["id"] + "_e0_candidate_input")
                fixtures.append((route["id"], inputs / "clean_source.obj", inputs / "clean_labels.json", assets / "inputs" / route["prefix_tools"][0]["mesh"]))
            report["scope"] = "两张已见公开肩胛骨首帧；静态机制开发，非独立或连续成功"
        for case, source, labels, tool in fixtures:
            folder = args.output / (case + "_planar")
            row = engine.run(source, labels, tool, "boolean", folder)
            row = audit_adaptive(source, tool, labels, folder, row)
            row["case"] = case
            report["rows"].append(row)
            save(args.output / "01-共面候选GPU开发记录.json", report)
            print(case, row["status"], row.get("free_vertices"), flush=True)
        report["status"] = "completed_with_recorded_failures"
        save(args.output / "01-共面候选GPU开发记录.json", report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
