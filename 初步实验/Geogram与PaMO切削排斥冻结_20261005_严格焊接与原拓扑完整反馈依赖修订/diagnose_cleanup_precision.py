"""只读核对去重精度与完整小面修复，不删除重复面或修改反馈算法。"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from exact_alarm_contact import mesh_valid_exact_contacts
from fragment_pipeline import repair_input
from locality_retriangulate import invalid_faces
from audit_followup_candidate import sha256


def diagnose(source, labels):
    """各精度独立从原网格开始，仅无重复面的副本进入原完整修复。"""
    raw=trimesh.load(source,force="mesh",process=False)
    bits=np.asarray(json.loads(labels.read_text(encoding="utf-8"))["operand_bits"])
    rows=[]
    for digits in range(16,7,-1):
        mesh=trimesh.Trimesh(vertices=raw.vertices.copy(),faces=raw.faces.copy(),process=False)
        mesh.merge_vertices(digits_vertex=digits)
        faces=mesh.faces
        keep=(faces[:,0]!=faces[:,1])&(faces[:,1]!=faces[:,2])&(faces[:,2]!=faces[:,0])
        mesh.update_faces(keep)
        mesh.remove_unreferenced_vertices()
        duplicate=len(mesh.faces)-len(np.unique(np.sort(mesh.faces,axis=1),axis=0))
        row={"digits_vertex":digits,"collapsed_faces":int((~keep).sum()),"duplicate_faces":int(duplicate)}
        if len(mesh.faces):
            row["raw_vertex_displacement_mm"]=float(cKDTree(mesh.vertices).query(raw.vertices)[0].max())
        if duplicate or not len(mesh.faces):
            row["status"]="duplicate_or_empty_rejected"
        elif row["raw_vertex_displacement_mm"]>1e-7:
            row["status"]="displacement_rejected"
        else:
            row["invalid_before"]=int(invalid_faces(mesh.vertices,mesh.faces).sum())
            _,before_metrics=mesh_valid_exact_contacts(mesh)
            row["topology_before"]={key:value for key,value in before_metrics.items()
                if isinstance(value,(bool,int,float,str)) or value is None}
            repaired,_,details=repair_input(mesh,bits[keep],audit=mesh_valid_exact_contacts,
                allow_shared=True,allow_small_incident=True)
            valid,metrics=mesh_valid_exact_contacts(repaired)
            row["valid_after"]=bool(valid and not metrics["fp32_zero_area_faces"])
            row["invalid_after"]=int(invalid_faces(repaired.vertices,repaired.faces).sum())
            row["topology_after"]={key:value for key,value in metrics.items()
                if isinstance(value,(bool,int,float,str)) or value is None}
            row["repair_passed"]=details.get("accepted",details.get("passed"))
            row["status"]="audited_candidate" if row["valid_after"] else "invalid_after_repair"
        rows.append(row)
    return {"source":str(source.resolve()),"source_sha256":sha256(source),
        "labels_sha256":sha256(labels),"precision_trials":rows}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--batch",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    record=json.loads((args.batch/"01-反馈执行与独立审计.json").read_text(encoding="utf-8"))
    results=[]
    for row in record["rows"]:
        if row.get("branch")=="candidate" and row.get("status")=="source_cleanup_rejected":
            folder=args.batch/(row["route"]+"_"+row["event"]+"_candidate_input")
            result=diagnose(folder/"source.obj",folder/"labels.json")
            result.update(route=row["route"],event=row["event"])
            results.append(result)
            print(row["route"],[(r["digits_vertex"],r["status"]) for r in result["precision_trials"]],flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({"time_beijing":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "scope":"同一已见输入的只读精度诊断，不是新连续成功或精度选择算法", "cases":results},ensure_ascii=False,indent=2),encoding="utf-8")
