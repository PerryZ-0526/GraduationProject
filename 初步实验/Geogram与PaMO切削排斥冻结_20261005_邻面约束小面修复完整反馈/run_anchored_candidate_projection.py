"""对修复后的实际源执行两种完整锚点投影诊断，不发布反馈状态。"""
import argparse
from pathlib import Path
from run_anchored_geometry_diagnostic import AnchoredEngine
from preserved_feedback_gate import audit_preserved_candidate
from run_geometry_study import now, save
from audit_followup_candidate import sha256


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "tool", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    # 各输入来自同一保存对象；记录实际摘要，不复用此前失败投影的结果。
    record = dict(time_beijing=now(), status="running", published=False, rows=[],
        input_sha256={name: sha256(getattr(args, name)) for name in ("source", "labels", "tool")})
    engine = AnchoredEngine(args.output, args.port)
    path = args.output/"01-修复源完整锚点投影诊断.json"
    try:
        record["environment"] = engine.setup()
        save(path, record)
        for method in ("boolean", "expanded"):
            folder = args.output/method
            row = engine.run(args.source, args.labels, args.tool, method, folder)
            row = audit_preserved_candidate(engine, args.source, args.tool, args.labels, folder, row)
            record["rows"].append(row)
            save(path, record)
            print(method, row["status"], row.get("numerical_diagnostic"), flush=True)
        record.update(status="completed_with_recorded_outcomes", finished_beijing=now())
        save(path, record)
    finally:
        engine.close()
