"""对冻结失败输入重新执行前置检查并保存检查前对象，不发布反馈状态。"""
import argparse
import shlex
from pathlib import Path
from run_anchored_geometry_diagnostic import AnchoredEngine
from preserved_controller_source import replace_once
from run_geometry_study import save, now, retrieve
from audit_followup_candidate import sha256
from preserved_feedback_gate import check_preserved_mesh
from run_preserved_geometry_feedback import EXPECTED_CHECKER
from audit_cut_embedding import CHECKER
from run_geometry_study import execute
import trimesh


class CaptureEngine(AnchoredEngine):
    def setup(self):
        info = super().setup()
        worker = (self.output / "run_anchored_worker.py").read_text(encoding="utf-8")
        # 仅提前保存证据；保持原前置拒绝和后续求解规则。
        worker = replace_once(worker,
            '        details["fixed_geometry_arithmetic_precondition"] = require_fixed_degenerate_faces(',
            '        save_obj_fp64(mesh, args.output / "before_precondition.obj")\n'
            '        np.savez(args.output / "precondition.npz", vertices=mesh.vertices, faces=mesh.faces, fixed=fixed, ids=ids, scale=geometry_scale, translation=geometry_translation)\n'
            '        details["fixed_geometry_arithmetic_precondition"] = require_fixed_degenerate_faces(')
        path = self.output / "capture_worker.py"
        path.write_text(worker, encoding="utf-8")
        self.sftp.put(str(path), self.remote + "/run_constrained_worker.py")
        info["capture_worker_sha256"] = sha256(path)
        return info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "tool", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    if not args.audit_only:
        args.output.mkdir(exist_ok=False)
    engine = CaptureEngine(args.output, args.port)
    record = dict(time_beijing=now(), published=False, status="running",
        provenance="冻结输入的新诊断复跑；不是原失败运行保存对象",
        inputs_sha256={name: sha256(getattr(args, name)) for name in ("source", "labels", "tool")})
    try:
        if args.audit_only:
            # 审计同一新诊断保存对象，不重新生成网格或改变旧失败状态。
            if execute(engine.client, ["sha256sum", CHECKER])["stdout"].split()[0] != EXPECTED_CHECKER:
                raise ValueError("精确检查器摘要变化")
            path = args.output / "boolean" / "before_precondition.obj"
            passed, metrics = check_preserved_mesh(engine, args.output / "full_geometry_checks",
                trimesh.load(path, process=False), "before_precondition")
            save(args.output / "03-同保存对象全量嵌入审计.json", dict(time_beijing=now(),
                passed=passed, metrics=metrics, published=False, saved_sha256=sha256(path)))
            print("full_exact_embedding", passed, flush=True)
            raise SystemExit(0)
        record["environment"] = engine.setup()
        save(args.output / "01-前置拒绝证据捕获.json", record)
        row = engine.run(args.source, args.labels, args.tool, "boolean", args.output / "boolean")
        command = shlex.split(row["execution"]["command"])
        remote = command[command.index("--output") + 1]
        for name in ("before_precondition.obj", "precondition.npz"):
            retrieve(engine.client, engine.sftp, remote + "/" + name, args.output / "boolean" / name)
        record.update(status="completed_with_recorded_outcome", row=row, finished_beijing=now())
        save(args.output / "01-前置拒绝证据捕获.json", record)
        print(row["status"], flush=True)
    finally:
        engine.close()
