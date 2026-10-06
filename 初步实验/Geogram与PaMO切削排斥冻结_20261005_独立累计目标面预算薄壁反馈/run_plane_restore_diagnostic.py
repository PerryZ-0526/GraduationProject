"""复现两个薄壁连续失败，区分CUDA求解与最终FP64平面恢复的面反向。"""
import argparse
import json
from run_collision_protected_feedback import ProtectedEngine
from run_constrained_batch import RemoteQuality,HERE
from run_geometry_study import retrieve,save,now


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",required=True,type=int)
    args=parser.parse_args()
    output=HERE/"实验结果/20261004_薄壁连续失败平面恢复诊断"
    output.mkdir(exist_ok=False)
    prior=HERE/"实验结果/20261004_碰撞数值保护多形状连续开发"
    prepared=HERE.parent/"可复用磨削测试集/开发浅磨批次_v1"
    routes=json.loads((prepared/"01-完整范围冻结清单.json").read_text(encoding="utf-8"))["routes"]
    engine=ProtectedEngine(output,args.port)
    report={"time_beijing":now(),"rows":[],"status":"running","scope":"已见薄壁失败复现；不发布结果"}
    try:
        report["environment"]=engine.setup()
        for rid,event in (("薄壁_00_浅磨","e2"),("薄壁_01_浅磨","e5")):
            route=next(r for r in routes if r["id"]==rid)
            tool=next(t for t in route["prefix_tools"] if t["event_id"]==event)
            inputs=prior/(rid+"_"+event+"_candidate_input")
            folder=output/(rid+"_"+event)
            row=RemoteQuality.run(engine,inputs/"clean_source.obj",inputs/"clean_labels.json",
                prepared/"inputs"/tool["mesh"],"planar_tangent_protected_shared",folder)
            failure=folder/"projection_failure.json"
            retrieve(engine.client,engine.sftp,engine.remote+"/"+folder.name+"/output/projection_failure.json",failure)
            row.update(route=rid,event=event,projection_failure=json.loads(failure.read_text(encoding="utf-8")))
            report["rows"].append(row)
            save(output/"01-薄壁平面恢复失败数值诊断.json",report)
            print(rid,event,row["projection_failure"]["stages"],flush=True)
        report.update(status="completed_failure_diagnostics",finished_beijing=now())
        save(output/"01-薄壁平面恢复失败数值诊断.json",report)
    finally:
        engine.close()


if __name__=="__main__":
    main()
