"""固定后端反馈的完整保存对象门控，FP32计数保留原值而不伪装为零。"""
import json
from pathlib import Path
import trimesh
from geometry_preservation_audit import mesh_valid
from exact_embedding_gate import stored_mesh_sha256
from audit_cut_embedding import CHECKER
from audit_followup_candidate import sha256
from locality_masks import save_obj_fp64
from opposed_facet_cleanup import clean_cancel_opposed
from run_opposed_pair_feedback import pair_repair
from preserved_input_repair import repair_preserved_input
from run_geometry_study import execute,save,now


def local_fp64_valid(mesh):
    _,metrics = mesh_valid(mesh)
    valid = all((metrics["finite"],metrics["zero_area_faces"] == 0,metrics["watertight"],
                 metrics["winding_consistent"],metrics["vertex_manifold_closed"]))
    return bool(valid),metrics


def check_preserved_mesh(engine,folder,mesh,role):
    valid,metrics = local_fp64_valid(mesh)
    metrics["arithmetic_policy"] = "保存FP64物理面积门槛不变；FP32退化须交原固定几何后端验证"
    if not valid:
        return False,metrics
    folder = Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    digest = stored_mesh_sha256(mesh)
    cache = getattr(engine,"preserved_embedding_cache",{})
    engine.preserved_embedding_cache = cache
    if digest not in cache:
        path = folder/(role+"_"+digest[:12]+".obj")
        save_obj_fp64(mesh,path)
        if sha256(path) != digest:
            raise ValueError("保存对象与全量嵌入绑定摘要不符")
        remote = engine.remote+"/embedding_"+digest+".obj"
        engine.sftp.put(str(path),remote)
        if execute(engine.client,["sha256sum",remote])["stdout"].split()[0] != digest:
            raise ValueError("实际远端全量嵌入输入摘要不符")
        run = execute(engine.client,[CHECKER,remote],timeout=120)
        certificate = dict(saved_sha256=digest,execution=run)
        if not run["returncode"]:
            certificate.update(json.loads(run["stdout"]))
        cache[digest] = certificate
    certificate = cache[digest]
    bound = certificate.get("saved_sha256") == digest
    metrics["full_exact_embedding"] = certificate
    metrics["historical_unresolved_alarm_faces"] = metrics["self_intersection_faces"]
    if certificate.get("embedded_closed") and bound:
        metrics["self_intersection_faces"] = 0
    metrics["full_exact_embedding_bound"] = bool(certificate.get("embedded_closed") and bound)
    save(folder/(role+"_"+digest[:12]+"_audit.json"),dict(time_beijing=now(),metrics=metrics))
    return bool(certificate.get("embedded_closed") and bound),metrics


def clean_for_backend(mesh,bits,branch):
    if branch == "full":
        return pair_repair(mesh,bits)
    clean,labels,details = clean_cancel_opposed(mesh,bits,allow_shared=True)
    repaired,labels,repair = repair_preserved_input(clean,labels)
    details["preserved_backend_repair"] = repair
    return repaired,labels,details


def repair_reference_input(mesh,bits):
    repaired,labels,record = repair_preserved_input(mesh,bits)
    # 仅给新独立参照版本提供原接口字段，不修改旧记录的接受结论。
    record = dict(record,accepted=record["accepted_for_fixed_geometry_backend"])
    return repaired,labels,record


def backend_methods(branch,labels_valid):
    # 原版独立配对保留；新固定几何候选不回退到不支持其输入前提的原版后端。
    return ("full",) if branch == "full" else ("boolean","expanded") if labels_valid else ()


def audit_preserved_candidate(engine,source_path,tool_path,labels_path,folder,row):
    import run_adaptive_feedback as adaptive
    if row["execution"]["returncode"]:
        return row
    candidate = trimesh.load(Path(folder)/"candidate.obj",process=False)
    valid,metrics = check_preserved_mesh(engine,Path(folder)/"full_geometry_checks",candidate,"candidate")
    # 全量证据只绑定同一候选；复用原几何、容量、来源固定及质量统计审计。
    previous = adaptive.mesh_valid
    adaptive.mesh_valid = lambda mesh: (valid,metrics) if stored_mesh_sha256(mesh) == stored_mesh_sha256(candidate) else local_fp64_valid(mesh)
    try:
        row = adaptive.audit_adaptive(source_path,tool_path,labels_path,folder,row)
    finally:
        adaptive.mesh_valid = previous
    if row["method"] != "full":
        numerical = row.get("numerical_diagnostic",{})
        if not numerical.get("passed") or not row.get("fixed_geometry_arithmetic_precondition",{}).get("all_degenerate_vertices_fixed"):
            row["status"] = "preserved_backend_numerical_or_binding_rejected"
    return row
