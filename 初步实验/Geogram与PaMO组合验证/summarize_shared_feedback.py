"""完整分母与同次维护质量汇总，区分原版、候选、复用及失败。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import trimesh
from audit_followup_candidate import quality_distribution,sha256
from geometry_preservation_audit import clearance,replay_primitives
from run_geometry_study import now,save


def median(values):
    return statistics.median(values) if values else None


def quality_changes(pairs):
    result={}
    for angle in (10,5,1):
        key=f"angle_below_{angle}_deg"
        entry={}
        for field in ("fraction","area_fraction"):
            deltas=[(b[key][field]-a[key][field])*100 for a,b in pairs
                    if a[key][field] is not None and b[key][field] is not None]
            entry[field]=dict(frames=len(deltas),median_change_percentage_points=median(deltas),
                improved=sum(x < -1e-10 for x in deltas),worsened=sum(x > 1e-10 for x in deltas),
                unchanged=sum(abs(x) <= 1e-10 for x in deltas))
        result[str(angle)]=entry
    return result


def selected_routes(routes, split):
    """按执行器记录的原split取完整分母，不混入同清单的其他批次。"""
    selected=[r for r in routes if r['split']==split]
    if not selected:
        raise ValueError('记录split在原冻结清单中没有路线')
    return selected


def summarize(prepared,output):
    path=prepared/"01-完整范围冻结清单.json"
    routes=json.loads(path.read_text(encoding="utf-8"))["routes"]
    record_path=output/"01-反馈执行与独立审计.json"
    record=json.loads(record_path.read_text(encoding="utf-8"))
    if record["status"] != "completed_with_recorded_failures":
        raise ValueError("只汇总完整终态；运行中不能推算后续接受")
    # 全范围清单含多个split，分母仍保留该次执行split的全部路线与事件。
    routes=selected_routes(routes,record['split'])
    keys=[(r["route"],r["event"],r["branch"]) for r in record["rows"]]
    if len(set(keys)) != len(keys):
        raise ValueError("存在重复物理事件记录")
    result=dict(time_beijing=now(),manifest_sha256=sha256(path),record_sha256=sha256(record_path),summarizer_sha256=sha256(Path(__file__)),branches={},rows=[],
        scope="同次维护输入输出比较，不以不同有效子集比较质量；邻域为同解析胶囊0.1毫米中心规则，非整面域证书")
    good=("published_under_sampled_and_vertex_protocol","contained_reused_parent")
    for branch in ("full","candidate"):
        selected=[r for r in record["rows"] if r["branch"]==branch]
        expected={(r["id"],e) for r in routes for e in r["cutting_prefix_ids"]}
        if {(r["route"],r["event"]) for r in selected} != expected:
            raise ValueError("完整计划分母缺失或含未登记事件")
        counts=Counter(r["status"] for r in selected)
        all_pairs,roi_pairs=[],[]
        for route in routes:
            route_rows=[r for r in selected if r["route"]==route["id"]]
            for row in route_rows:
                if row["status"] != "published_under_sampled_and_vertex_protocol":
                    continue
                stem=row["route"]+"_"+row["event"]+"_"+branch
                # 断连合并记录保留每行原目录；普通批次继续读取当前输出目录。
                source_root=Path(row.get("source_output_directory",output))
                source=trimesh.load(source_root/(stem+"_input")/"clean_source.obj",process=False)
                primitives=replay_primitives(route,row["event"])
                active=clearance(source.triangles_center,primitives) <= .1
                source_roi=quality_distribution(trimesh.Trimesh(source.vertices,source.faces[active],process=False))
                attempt=next(a for a in row["attempts"] if a["status"]=="accepted_sampled")
                all_pairs.append((attempt["source_quality"],row["preservation"]["quality_all"]))
                roi_pairs.append((source_roi,row["preservation"]["quality_sweep_margin_roi"]))
                result["rows"].append(dict(route=row["route"],event=row["event"],branch=branch,
                    source_all=attempt["source_quality"],output_all=row["preservation"]["quality_all"],
                    source_roi=source_roi,output_roi=row["preservation"]["quality_sweep_margin_roi"],
                    protected_vertices=attempt.get("collision_protected_vertices",[]),
                    remaining_free_vertices=attempt.get("remaining_free_vertices")))
        complete=[r["id"] for r in routes if all(x["status"] in good for x in selected if x["route"]==r["id"])]
        result["branches"][branch]=dict(planned_routes=len(routes),planned_events=len(expected),status_counts=dict(counts),
            covered_events=sum(x["status"] in good for x in selected),complete_routes=complete,
            published_methods=dict(Counter(x["selected_method"] for x in selected if x["status"]==good[0])),
            same_maintenance_all=quality_changes(all_pairs),same_maintenance_roi=quality_changes(roi_pairs))
    save(output/"06-完整分母与同次维护区域质量统计.json",result)
    print({k:(v["covered_events"],len(v["complete_routes"])) for k,v in result["branches"].items()})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    summarize(args.prepared,args.output)
