"""在用户GPU上同源复现薄壁后续求导拒绝，并保留成功初刀作为控制。"""
import argparse
import json
from pathlib import Path
from run_patch_area_guard_feedback import AreaGuardEngine
from run_constrained_batch import HERE,RemoteQuality
from run_geometry_study import save,now,retrieve
from audit_followup_candidate import sha256


class DiagnosticEngine(AreaGuardEngine):
    def setup(self):
        info=super().setup()
        module=HERE/"collision_diff_diagnostic.py"
        worker=(HERE/"run_planar_worker.py").read_text(encoding="utf-8")
        original="from collision_protected_gpu import CollisionProtectedSystem"
        if worker.count(original)!=1:
            raise ValueError("诊断替换要求唯一原碰撞保护导入")
        snapshot=self.output/"run_diagnostic_worker.py"
        snapshot.write_text(worker.replace(original,"from collision_diff_diagnostic import CollisionProtectedSystem"),encoding="utf-8")
        self.sftp.put(str(snapshot),self.remote+"/run_constrained_worker.py")
        self.sftp.put(str(module),self.remote+"/"+module.name)
        (self.output/module.name).write_bytes(module.read_bytes())
        info["diagnostic_code_sha256"]={module.name:sha256(module),snapshot.name:sha256(snapshot)}
        return info


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--port",required=True,type=int)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    prior=HERE/"实验结果/20261004_局部质量28体连续评价_异常记录修订"
    prepared=HERE.parent/"可复用磨削测试集/局部质量独立插值输入_v3"
    manifest=json.loads((prepared/"01-完整范围冻结清单.json").read_text(encoding="utf-8"))
    route=next(r for r in manifest["routes"] if r["id"]=="薄壁_新参数2p25_交叉")
    engine=DiagnosticEngine(args.output,args.port)
    report={"time_beijing":now(),"status":"running","rows":[],"scope":"同源数值诊断，保持原拒绝，不发布结果"}
    try:
        report["environment"]=engine.setup()
        for event,method in (("e1","boolean"),("e1","expanded"),("e0","boolean")):
            # 每轮独立CUDA进程，仅清除本诊断目录的旧观测文件以防串帧。
            for name in ("diff_trace.json","diff_failure_positions.npz"):
                try:
                    engine.sftp.remove(engine.remote+"/"+name)
                except FileNotFoundError:
                    pass
            tool=next(t for t in route["prefix_tools"] if t["event_id"]==event)
            folder=args.output/(event+"_"+method)
            inputs=prior/(route["id"]+"_"+event+"_candidate_input")
            result=engine.run(inputs/"clean_source.obj",inputs/"clean_labels.json",prepared/"inputs"/tool["mesh"],method,folder)
            retrieve(engine.client,engine.sftp,engine.remote+"/diff_trace.json",folder/"diff_trace.json")
            if result["status"]=="execution_failed":
                retrieve(engine.client,engine.sftp,engine.remote+"/diff_failure_positions.npz",folder/"diff_failure_positions.npz")
            trace=json.loads((folder/"diff_trace.json").read_text(encoding="utf-8"))
            report["rows"].append({"event":event,"method":method,"result":result,"trace":trace})
            save(args.output/"01-薄壁后续求导分项诊断.json",report)
            print(event,method,result["status"],trace["rows"][-1],flush=True)
        report.update(status="completed_diagnostics",finished_beijing=now())
        save(args.output/"01-薄壁后续求导分项诊断.json",report)
    finally:
        engine.close()
