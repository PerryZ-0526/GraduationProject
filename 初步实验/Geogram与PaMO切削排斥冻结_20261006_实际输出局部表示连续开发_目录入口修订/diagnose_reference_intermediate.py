"""在独立新目录验证已绑定参照失败输入的修复，不改旧批次或发布状态。"""
import argparse
import json
from pathlib import Path
import trimesh
from audit_followup_candidate import sha256
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, retrieve, save, now, GEO
from preserved_feedback_gate import check_preserved_mesh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--certificates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    certificates = json.loads(args.certificates.read_text(encoding="utf-8"))
    paths = [args.input/"repaired_parent_not_published.obj", args.input/"tool.obj"]
    # 仅允许本轮已通过同文件全量嵌入的两个冻结操作数。
    for path in paths:
        match = [row for row in certificates["rows"] if row["sha256"] == sha256(path)]
        if len(match) != 1 or not match[0].get("embedded_closed"):
            raise ValueError("操作数缺少绑定完整嵌入证据")
    args.output.mkdir(exist_ok=False)
    engine = RemoteQuality(args.output, args.port)
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise RuntimeError("新诊断目录创建失败")
        remote_paths = []
        for index, path in enumerate(paths):
            remote = engine.remote+"/operand_"+str(index)+".obj"
            engine.sftp.put(str(path), remote)
            if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
                raise ValueError("上传操作数摘要不符")
            remote_paths.append(remote)
        target = engine.remote+"/result.obj"
        run = execute(engine.client, [GEO, *remote_paths, target], target+".log", timeout=120)
        retrieve(engine.client, engine.sftp, target+".log", args.output/"geogram.log")
        record = dict(time_beijing=now(), execution=run,
            operands=[dict(path=str(p), sha256=sha256(p)) for p in paths],
            scope="实际失败参照的修复操作数新诊断；没有候选父网格，不发布、不改原138步记录")
        if not run["returncode"]:
            retrieve(engine.client, engine.sftp, target, args.output/"raw_result.obj")
            mesh = trimesh.load(args.output/"raw_result.obj", process=False)
            valid, metrics = check_preserved_mesh(engine, args.output/"checks", mesh, "raw_result")
            record.update(raw_result_valid=valid, raw_result_metrics=metrics)
        save(args.output/"01-参照中间输入修复布尔诊断.json", record)
        print("boolean returncode", run["returncode"], "raw valid", record.get("raw_result_valid"))
    finally:
        engine.close()


if __name__ == "__main__":
    main()
