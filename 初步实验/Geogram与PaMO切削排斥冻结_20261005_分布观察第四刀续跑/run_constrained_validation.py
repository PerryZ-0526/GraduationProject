"""开发闭环之后串行完成长序列、应用、独立路线和新小特征批次。"""

import argparse
import getpass
from pathlib import Path
import sys

from audit_followup_candidate import sha256
from run_geometry_study import now, save
import run_constrained_feedback as feedback
import run_constrained_features as features
import audit_constrained_feedback as feedback_audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    here = Path(__file__).resolve().parent
    names = ["constrained_remesh.cpp", "constrained_quality.py", "run_constrained_worker.py",
             "run_constrained_batch.py", "run_constrained_feedback.py", "run_constrained_features.py",
             "locality_masks.py", "locality_gpu.py", "geometry_preservation_audit.py", "locality_diagnostic.py",
             "locality_cleanup.py", "audit_constrained_feedback.py", "run_constrained_validation.py"]
    record = {"time_beijing": now(), "status": "running", "stages": [],
        "code_sha256": {name: sha256(here / name) for name in names},
        "input_manifest_sha256": sha256(args.prepared / "01-完整范围冻结清单.json"),
        "independent_policy": "method_and_inputs_frozen_before_new_evaluation; no_retuning_after_open"}
    save(args.output / "01-全范围冻结与执行账本.json", record)
    original_getpass = getpass.getpass
    credential = original_getpass("GPU SSH password: ")
    # 密码只在本次进程内复用，避免串行批次重复询问；不写入文件或命令。
    getpass.getpass = lambda *args, **kwargs: credential
    original_argv = sys.argv.copy()
    try:
        for split in ("long", "application", "evaluation", "features"):
            for name, expected in record["code_sha256"].items():
                if sha256(here / name) != expected:
                    raise ValueError("方法已冻结，批次中检测到源码变更：" + name)
            output = args.output / split
            stage = {"name": split, "started_beijing": now(), "status": "running"}
            record["stages"].append(stage)
            save(args.output / "01-全范围冻结与执行账本.json", record)
            sys.argv = ["validation", "--prepared", str(args.prepared), "--output", str(output), "--port", str(args.port)]
            if split == "features":
                features.main()
            else:
                sys.argv += ["--split", split]
                feedback.main()
                # 执行结束后核对完整计划分母及真实父链，失败结果仍计入报告。
                sys.argv = ["audit", "--prepared", str(args.prepared), "--output", str(output)]
                feedback_audit.main()
            stage.update(status="execution_finished_results_require_completion_audit", finished_beijing=now())
            save(args.output / "01-全范围冻结与执行账本.json", record)
        record.update(status="all_stages_finished_requires_completion_audit", finished_beijing=now())
        save(args.output / "01-全范围冻结与执行账本.json", record)
    except BaseException as error:
        record.update(status="interrupted_infrastructure_requires_recovery", error=type(error).__name__ + ": " + str(error))
        save(args.output / "01-全范围冻结与执行账本.json", record)
        raise
    finally:
        getpass.getpass = original_getpass
        sys.argv = original_argv
        del credential


if __name__ == "__main__":
    main()
