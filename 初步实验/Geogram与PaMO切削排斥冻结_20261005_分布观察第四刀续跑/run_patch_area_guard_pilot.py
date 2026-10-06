"""两个薄壁失败输入同源对照，检查区域面积保护的收益与代价。"""
import argparse
import json
from run_collision_protected_feedback import ProtectedEngine
from run_constrained_batch import RemoteQuality,HERE
from run_adaptive_feedback import audit_adaptive
import run_adaptive_feedback as adaptive
from exact_alarm_contact import mesh_valid_exact_contacts
from run_geometry_study import save,now


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",required=True,type=int)
    args=parser.parse_args()
    output=HERE/"实验结果/20261004_薄壁区域面积保护GPU对照"
    output.mkdir(exist_ok=False)
    prior=HERE/"实验结果/20261004_碰撞数值保护多形状连续开发"
    prepared=HERE.parent/"可复用磨削测试集/开发浅磨批次_v1"
    routes=json.loads((prepared/"01-完整范围冻结清单.json").read_text(encoding="utf-8"))["routes"]
    engine=ProtectedEngine(output,args.port)
    adaptive.mesh_valid=mesh_valid_exact_contacts
    report={"time_beijing":now(),"rows":[],"status":"running","scope":"已见失败静态配对；不改写旧连续记录"}
    try:
        report["environment"]=engine.setup()
        for rid,event in (("薄壁_00_浅磨","e2"),("薄壁_01_浅磨","e5")):
            route=next(r for r in routes if r["id"]==rid)
            tool=next(t for t in route["prefix_tools"] if t["event_id"]==event)
            inputs=prior/(rid+"_"+event+"_candidate_input")
            for method in ("planar_tangent_protected_shared","planar_tangent_protected_areaguard_shared"):
                folder=output/(rid+"_"+event+"_"+method)
                source,labels=inputs/"clean_source.obj",inputs/"clean_labels.json"
                row=RemoteQuality.run(engine,source,labels,prepared/"inputs"/tool["mesh"],method,folder)
                row=audit_adaptive(source,prepared/"inputs"/tool["mesh"],labels,folder,row)
                report["rows"].append(dict(row,route=rid,event=event))
                save(output/"01-区域面积保护两输入执行记录.json",report)
                print(rid,event,method,row["status"],flush=True)
        report.update(status="completed_with_recorded_failures",finished_beijing=now())
        save(output/"01-区域面积保护两输入执行记录.json",report)
    finally:
        engine.close()


if __name__=="__main__":
    main()
