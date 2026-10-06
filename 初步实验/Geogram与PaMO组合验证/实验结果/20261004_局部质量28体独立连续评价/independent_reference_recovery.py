"""从原初态重放工具并审查参照，独立于维护网格及其父链。"""
import numpy as np
import trimesh
from fragment_pipeline import repair_input
from locality_cleanup import clean_provenance
from exact_alarm_contact import mesh_valid_exact_contacts
from locality_masks import save_obj_fp64
from recover_public_reference import prefix_tools_through
from run_constrained_feedback import global_geometry
from run_geometry_study import execute,retrieve,GEO
from audit_followup_candidate import sha256


def validate_replayed_reference(raw):
    """修复只接受闭合合法且与原始重放表面探针差异不超过1e-7毫米的参照。"""
    # 统一标签只服务参照整体的平面操作，不冒充CSG操作数来源。
    clean,labels,cleanup=clean_provenance(raw,np.ones(len(raw.faces),int))
    repaired,_,repair=repair_input(clean,labels,audit=mesh_valid_exact_contacts)
    geometry=global_geometry(repaired,raw)
    valid,metrics=mesh_valid_exact_contacts(repaired)
    accepted=bool(repair["accepted"] and valid and geometry["probe_max_mm"] <= 1e-7)
    return repaired if accepted else None,dict(accepted=accepted,cleanup=cleanup,repair=repair,
        raw_to_repaired_geometry=geometry,validated_metrics=metrics)


def recover_reference(engine,prepared,route,event,initial_remote,folder,reuse):
    """失败时顺序重放；已恢复参照可在已判定扫掠包含的事件中按哈希复用。"""
    cache=getattr(engine,"independent_reference_cache",{})
    engine.independent_reference_cache=cache
    rid=route["id"]
    record=dict(accepted=False,route=rid,event=event,
        independence="原初态及截至事件的原工具，不使用维护父网格",runs=[],
        continuous_geometry_certified=False)
    destination=folder/"validated_reference.obj"
    if reuse and rid in cache:
        prior,expected,metrics=cache[rid]
        if sha256(prior) != expected:
            raise ValueError("缓存恢复参照摘要变化")
        destination.write_bytes(prior.read_bytes())
        record.update(accepted=True,kind="contained_reused_recovered_reference",reused_sha256=expected,
                      validated_metrics=metrics,output_sha256=sha256(destination))
        return trimesh.load(destination,process=False),record
    # 新切削不能沿用未包含该刀的旧参照，即使当前恢复随后失败也清除旧缓存。
    cache.pop(rid,None)
    tools=prefix_tools_through(route,event)
    initial=prepared/"inputs"/route["initial_mesh"]
    if sha256(initial) != route["initial_mesh_sha256"]:
        raise ValueError("独立重放初态摘要变化")
    # 使用本机冻结初态重新上传，避免任何候选父路径混入。
    parent=engine.remote+"/"+rid+"_"+event+"_recovery_initial.obj"
    engine.sftp.put(str(initial),parent)
    record.update(initial_sha256=sha256(initial),tool_events=[t["event_id"] for t in tools],tool_sha256=[t["sha256"] for t in tools])
    for tool in tools:
        source=prepared/"inputs"/tool["mesh"]
        if sha256(source) != tool["sha256"]:
            raise ValueError("独立重放工具摘要变化")
        remote_tool=engine.remote+"/"+rid+"_"+event+"_recovery_tool_"+tool["event_id"]+".obj"
        output=engine.remote+"/"+rid+"_"+event+"_recovery_after_"+tool["event_id"]+".obj"
        engine.sftp.put(str(source),remote_tool)
        run=execute(engine.client,[GEO,parent,remote_tool,output],output+".log",timeout=120)
        retrieve(engine.client,engine.sftp,output+".log",folder/("recovery_"+tool["event_id"]+".log"))
        record["runs"].append(run)
        if run["returncode"]:
            record["status"]="sequential_replay_failed"
            return None,record
        parent=output
    raw_path=folder/"sequential_replay_raw.obj"
    retrieve(engine.client,engine.sftp,parent,raw_path)
    raw=trimesh.load(raw_path,process=False)
    repaired,validation=validate_replayed_reference(raw)
    record.update(validation,kind="independent_sequential_replay",raw_sha256=sha256(raw_path))
    if repaired is not None:
        save_obj_fp64(repaired,destination)
        # 最终保存格式再加载核查，复用仅认定同一个已核查保存对象。
        saved=trimesh.load(destination,process=False)
        valid,metrics=mesh_valid_exact_contacts(saved)
        if not valid or global_geometry(saved,raw)["probe_max_mm"] > 1e-7:
            record.update(accepted=False,status="saved_reference_rejected")
            return None,record
        record.update(validated_metrics=metrics,output_sha256=sha256(destination))
        cache[rid]=(destination,record["output_sha256"],metrics)
        return saved,record
    return None,record
