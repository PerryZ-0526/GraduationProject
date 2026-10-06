"""三张数值失败及两张成功开发输入的固定碰撞保护对照。"""
import argparse
import json
from pathlib import Path
from run_collision_protected_feedback import ProtectedEngine
from run_constrained_batch import RemoteQuality,HERE
from run_adaptive_feedback import audit_adaptive
import run_adaptive_feedback as adaptive
from exact_alarm_contact import mesh_valid_exact_contacts
from audit_followup_candidate import sha256
from run_geometry_study import now,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",required=True,type=int)
    args=parser.parse_args()
    output=HERE/"实验结果/20261004_碰撞导数保护五输入GPU对照"
    output.mkdir(exist_ok=False)
    engine=ProtectedEngine(output,args.port)
    adaptive.mesh_valid=mesh_valid_exact_contacts
    report=dict(time_beijing=now(),rows=[],status="running",scope="三张已见失败及两张已见成功输入；非独立评价")
    cases=[("公开右肩胛长磨失败","20261004_共同来源碎片修复公开长路线","BP3D_FJ3384_重复长磨","e3","公开重复长磨批次_v1"),
           ("薄壁零号失败","20261004_共同来源碎片修复多形状开发","薄壁_00_浅磨","e1","开发浅磨批次_v1"),
           ("薄壁一号失败","20261004_共同来源碎片修复多形状开发","薄壁_01_浅磨","e1","开发浅磨批次_v1"),
           ("公开肩胛首帧成功","20261004_共同来源碎片修复公开骨面反馈","BP3D_FJ3384_交叉浅磨","e0","公开浅磨批次_v2"),
           ("球体首帧成功","20261004_共同来源碎片修复多形状开发","球体_00_浅磨","e0","开发浅磨批次_v1")]
    try:
        report["environment"]=engine.setup()
        report["cases"]=cases
        save(output/"01-碰撞保护五输入执行记录.json",report)
        for case,batch,rid,event,assets in cases:
            prepared=HERE.parent/"可复用磨削测试集"/assets
            route=next(r for r in json.loads((prepared/"01-完整范围冻结清单.json").read_text(encoding="utf-8"))["routes"] if r["id"]==rid)
            info=next(t for t in route["prefix_tools"] if t["event_id"]==event)
            inputs=HERE/"实验结果"/batch/(rid+"_"+event+"_candidate_input")
            source,labels,tool=inputs/"clean_source.obj",inputs/"clean_labels.json",prepared/"inputs"/info["mesh"]
            for method in ("planar_tangent_shared","planar_tangent_protected_shared"):
                folder=output/(case+"_"+method)
                row=RemoteQuality.run(engine,source,labels,tool,method,folder)
                row=audit_adaptive(source,tool,labels,folder,row)
                row["case"]=case
                report["rows"].append(row)
                save(output/"01-碰撞保护五输入执行记录.json",report)
                print(case,method,row["status"],row.get("collision_protected_vertices"),row.get("remaining_free_vertices"),flush=True)
        report.update(status="completed_with_recorded_failures",finished_beijing=now())
        save(output/"01-碰撞保护五输入执行记录.json",report)
    finally:
        engine.close()


if __name__=="__main__":
    main()
