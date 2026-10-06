"""同步追加锚点的隔离完整投影诊断，不发布或修改旧失败批次。"""
import argparse
import json
from pathlib import Path
import shlex
from run_preserved_geometry_feedback import PreservedFeedbackEngine
from run_constrained_batch import HERE
from preserved_controller_source import replace_once
from preserved_feedback_gate import audit_preserved_candidate
from run_geometry_study import retrieve, save, now
from audit_followup_candidate import sha256


class AnchoredEngine(PreservedFeedbackEngine):
    def setup(self):
        info = super().setup()
        for name in ("fixed_anchor_contract.py", "anchored_geometry_system.py"):
            (self.output/name).write_bytes((HERE/name).read_bytes())
            self.sftp.put(str(HERE/name), self.remote+"/"+name)
        worker = (self.output/"run_preserved_feedback_worker.py").read_text(encoding="utf-8")
        worker = replace_once(worker, "from preserved_geometry_system import CollisionProtectedSystem",
            "from anchored_geometry_system import CollisionProtectedSystem")
        path = self.output/"run_anchored_worker.py"
        path.write_text(worker, encoding="utf-8")
        self.sftp.put(str(path), self.remote+"/run_constrained_worker.py")
        info.update(anchor_contract_sha256=sha256(HERE/"fixed_anchor_contract.py"),
            anchor_system_sha256=sha256(HERE/"anchored_geometry_system.py"), actual_anchored_worker_sha256=sha256(path))
        return info

    def run(self, source, labels, tool, method, folder):
        row = super().run(source, labels, tool, method, folder)
        if method != "full":
            try:
                retrieve(self.client, self.sftp, self.remote+"/anchor_updates.json", Path(folder)/"anchor_updates.json")
                self.sftp.rename(self.remote+"/anchor_updates.json", self.remote+"/"+Path(folder).name+"_anchor_updates.json")
                row["anchor_updates"] = json.loads((Path(folder)/"anchor_updates.json").read_text(encoding="utf-8"))
            except FileNotFoundError:
                # 输入前置拒绝或零自由度恒等返回没有锚点运行记录，保留实际原因。
                row["anchor_record_available"] = False
                if row.get("projection") != "no_free_vertices_identity":
                    row["numerical_diagnostic"]["passed"] = False
        return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "tool", "output", "baseline"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    record = dict(time_beijing=now(), published=False, rows=[], status="running",
        input_sha256={name:sha256(getattr(args,name)) for name in ("source","labels","tool")})
    engine = AnchoredEngine(args.output, args.port)
    try:
        record["environment"] = engine.setup()
        save(args.output/"01-追加锚点完整投影隔离诊断.json", record)
        for method in ("boolean", "expanded"):
            folder = args.output/method
            row = engine.run(args.source, args.labels, args.tool, method, folder)
            row = audit_preserved_candidate(engine, args.source, args.tool, args.labels, folder, row)
            # 实际输出路径从同次执行命令读取，不能推测或用重建网格代替基线对象。
            command = shlex.split(row["execution"]["command"])
            remote = command[command.index("--output")+1]+"/before_projection.obj"
            retrieve(engine.client, engine.sftp, remote, folder/"before_projection.obj")
            row["same_before_projection_as_failed_baseline"] = sha256(folder/"before_projection.obj") == sha256(args.baseline/method/"before_projection.obj")
            record["rows"].append(row)
            save(args.output/"01-追加锚点完整投影隔离诊断.json", record)
            print(method, row["status"], row["numerical_diagnostic"], row["anchor_updates"], flush=True)
        record.update(status="completed_with_recorded_outcomes", finished_beijing=now())
        save(args.output/"01-追加锚点完整投影隔离诊断.json", record)
    finally:
        engine.close()
