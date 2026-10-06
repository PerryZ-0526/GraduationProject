"""三个同源GPU投影对照，独立审查输出，不进入连续发布状态机。"""
import argparse
import json
from pathlib import Path
import run_adaptive_feedback as adaptive
from exact_alarm_contact import mesh_valid_exact_contacts
from run_derivative_failure_diagnostic import DiagnosticEngine
from run_constrained_batch import HERE
from run_geometry_study import save,now,retrieve
from audit_followup_candidate import sha256


class PrecisionEngine(DiagnosticEngine):
    def setup(self):
        info=super().setup()
        names=("robust_pt_gpu.py","precision_collision_install.py","precision_collision_system.py")
        for name in names:
            self.sftp.put(str(HERE/name),self.remote+"/"+name)
            (self.output/name).write_bytes((HERE/name).read_bytes())
        worker=(self.output/"run_diagnostic_worker.py").read_text(encoding="utf-8")
        marker="from collision_diff_diagnostic import CollisionProtectedSystem"
        if worker.count(marker)!=1:
            raise ValueError("精度投影要求唯一诊断系统导入")
        snapshot=self.output/"run_precision_worker.py"
        snapshot.write_text(worker.replace(marker,"from precision_collision_system import CollisionProtectedSystem"),encoding="utf-8")
        self.sftp.put(str(snapshot),self.remote+"/run_constrained_worker.py")
        info["precision_code_sha256"]={name:sha256(HERE/name) for name in names}
        info["actual_worker_sha256"]=sha256(snapshot)
        return info


def main(engine_type=PrecisionEngine):
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    prior=HERE/"实验结果/20261004_局部质量28体连续评价_异常记录修订"
    prepared=HERE.parent/"可复用磨削测试集/局部质量独立插值输入_v3"
    route=next(r for r in json.loads((prepared/"01-完整范围冻结清单.json").read_text(encoding="utf-8"))["routes"] if r["id"]=="薄壁_新参数2p25_交叉")
    engine=engine_type(args.output,args.port)
    report={"time_beijing":now(),"status":"running","rows":[],"scope":"已见薄壁同源GPU数值改进，不是连续路线成功"}
    adaptive.mesh_valid=mesh_valid_exact_contacts
    try:
        report["environment"]=engine.setup()
        for event,method in [("e1","boolean"),("e1","expanded"),("e0","boolean")]:
            try:
                engine.sftp.remove(engine.remote+"/diff_trace.json")
            except FileNotFoundError:
                pass
            folder=args.output/(event+"_"+method)
            inputs=prior/(route["id"]+"_"+event+"_candidate_input")
            tool=next(t for t in route["prefix_tools"] if t["event_id"]==event)
            tool_path=prepared/"inputs"/tool["mesh"]
            result=engine.run(inputs/"clean_source.obj",inputs/"clean_labels.json",tool_path,method,folder)
            retrieve(engine.client,engine.sftp,engine.remote+"/"+folder.name+"/output/before_projection.obj",folder/"before_projection.obj")
            retrieve(engine.client,engine.sftp,engine.remote+"/diff_trace.json",folder/"diff_trace.json")
            if result["status"]!="execution_failed":
                result=adaptive.audit_adaptive(inputs/"clean_source.obj",tool_path,inputs/"clean_labels.json",folder,result)
            trace=json.loads((folder/"diff_trace.json").read_text(encoding="utf-8"))
            report["rows"].append({"event":event,"method":method,"result":result,"trace":trace})
            save(args.output/"01-FP64碰撞分类完整投影对照.json",report)
            print(event,method,result["status"],len(trace["rows"]),flush=True)
        report.update(status="completed_with_recorded_results",finished_beijing=now())
        save(args.output/"01-FP64碰撞分类完整投影对照.json",report)
    finally:
        engine.close()


if __name__=="__main__":
    main()
