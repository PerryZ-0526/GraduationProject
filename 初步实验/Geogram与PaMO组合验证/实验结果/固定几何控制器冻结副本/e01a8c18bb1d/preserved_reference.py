"""独立参照逐步修复并绑定全量嵌入，避免将破损中间网格送入下一次布尔。"""
import numpy as np
import trimesh
from audit_followup_candidate import sha256
from locality_masks import save_obj_fp64
from ordered_physical_cleanup import ordered_cancel_opposed as clean_cancel_opposed
from physical_input_repair import repair_physical_input as repair_preserved_input
from preserved_feedback_gate import check_preserved_mesh
from recover_public_reference import prefix_tools_through
from run_constrained_feedback import global_geometry
from run_geometry_study import execute, retrieve, GEO


def recover_reference(engine, prepared, route, event, initial_remote, folder, reuse):
    cache = getattr(engine, "guarded_reference_cache", {})
    engine.guarded_reference_cache = cache
    rid = route["id"]
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder/"validated_reference.obj"
    record = dict(accepted=False, route=rid, event=event, runs=[], steps=[],
        independence="仅原初态与截至事件原工具；每步独立修复，不使用维护父网格",
        continuous_geometry_certified=False)
    if reuse and rid in cache:
        path, digest, metrics = cache[rid]
        if sha256(path) != digest:
            raise ValueError("逐步参照缓存摘要变化")
        destination.write_bytes(path.read_bytes())
        record.update(accepted=True, kind="contained_reused_guarded_reference", output_sha256=digest,
            validated_metrics=metrics)
        return trimesh.load(destination, process=False), record
    cache.pop(rid, None)
    initial = prepared/"inputs"/route["initial_mesh"]
    if sha256(initial) != route["initial_mesh_sha256"]:
        raise ValueError("原初态摘要变化")
    tools = prefix_tools_through(route, event)
    record.update(initial_sha256=sha256(initial), tool_events=[t["event_id"] for t in tools],
        tool_sha256=[t["sha256"] for t in tools])
    parent = engine.remote+"/"+rid+"_"+event+"_guarded_initial.obj"
    engine.sftp.put(str(initial), parent)
    valid, metrics = check_preserved_mesh(engine, folder/"initial_checks",
        trimesh.load(initial, process=False), "initial")
    record["initial_metrics"] = metrics
    if not valid:
        record["status"] = "initial_rejected"
        return None, record
    for tool in tools:
        source = prepared/"inputs"/tool["mesh"]
        if sha256(source) != tool["sha256"]:
            raise ValueError("原工具摘要变化")
        step = folder/tool["event_id"]
        step.mkdir(exist_ok=False)
        remote_tool = parent+"_tool.obj"
        output = parent+"_result.obj"
        engine.sftp.put(str(source), remote_tool)
        run = execute(engine.client, [GEO, parent, remote_tool, output], output+".log", timeout=120)
        retrieve(engine.client, engine.sftp, output+".log", step/"geogram.log")
        record["runs"].append(run)
        if run["returncode"]:
            record["status"] = "guarded_replay_boolean_failed"
            return None, record
        raw_path = step/"raw.obj"
        retrieve(engine.client, engine.sftp, output, raw_path)
        raw = trimesh.load(raw_path, process=False)
        try:
            clean, bits, cleanup = clean_cancel_opposed(raw, np.ones(len(raw.faces), int), allow_shared=True)
            mesh, _, repair = repair_preserved_input(clean, bits)
        except ValueError as error:
            record.update(status="guarded_replay_cleanup_rejected", error=str(error))
            return None, record
        saved_path = step/"repaired.obj"
        save_obj_fp64(mesh, saved_path)
        saved = trimesh.load(saved_path, process=False)
        geometry = global_geometry(saved, raw)
        valid, metrics = check_preserved_mesh(engine, step/"checks", saved, "reference_step")
        accepted = bool(repair["accepted_for_fixed_geometry_backend"] and valid and geometry["probe_max_mm"] <= 1e-7)
        record["steps"].append(dict(event=tool["event_id"], raw_sha256=sha256(raw_path),
            saved_sha256=sha256(saved_path), cleanup=cleanup, repair=repair,
            raw_to_repaired_geometry=geometry, validated_metrics=metrics, accepted=accepted))
        if not accepted:
            record["status"] = "guarded_replay_intermediate_rejected"
            return None, record
        # 下一步只读取同一个已保存、全量核查并上传摘要匹配的中间对象。
        parent = engine.remote+"/"+rid+"_"+event+"_guarded_after_"+tool["event_id"]+".obj"
        engine.sftp.put(str(saved_path), parent)
        if execute(engine.client, ["sha256sum", parent])["stdout"].split()[0] != sha256(saved_path):
            raise ValueError("逐步参照上传摘要变化")
    destination.write_bytes(saved_path.read_bytes())
    record.update(accepted=True, status="guarded_replay_complete", kind="independent_guarded_replay",
        output_sha256=sha256(destination), validated_metrics=metrics)
    cache[rid] = (destination, record["output_sha256"], metrics)
    return saved, record
