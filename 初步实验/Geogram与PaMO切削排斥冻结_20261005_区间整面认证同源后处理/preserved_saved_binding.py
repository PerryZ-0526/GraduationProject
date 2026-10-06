"""保存对象复审只能使用完整执行成功且绑定同一对象的精确嵌入证据。"""
from exact_embedding_gate import stored_mesh_sha256
from preserved_feedback_gate import local_fp64_valid
import trimesh


def load_bound_reference(path,row):
    """原参照保留原加载协议；恢复参照按发布时已核验保存对象直接加载。"""
    recovered = bool(row.get("reference_used_file"))
    return trimesh.load(path,process=not recovered,validate=not recovered)


def collect_certificates(value):
    certificates = {}
    def visit(item):
        if isinstance(item,dict):
            certificate = item.get("full_exact_embedding")
            if certificate is not None:
                digest = certificate.get("saved_sha256")
                if digest in certificates and certificates[digest] != certificate:
                    raise ValueError("同一保存对象出现不同精确证据")
                certificates[digest] = certificate
            for child in item.values():
                visit(child)
        elif isinstance(item,list):
            for child in item:
                visit(child)
    visit(value)
    return certificates


def mesh_valid_saved_binding(mesh,certificates):
    valid,metrics = local_fp64_valid(mesh)
    digest = stored_mesh_sha256(mesh)
    certificate = certificates.get(digest,{})
    bound = all((certificate.get("saved_sha256") == digest,certificate.get("embedded_closed") is True,
                 certificate.get("execution",{}).get("returncode") == 0,
                 certificate.get("parsed") is True,certificate.get("topology_valid") is True,
                 certificate.get("closed") is True,certificate.get("self_intersection_pairs") == 0))
    metrics["full_exact_embedding_bound"] = bool(bound)
    metrics["historical_unresolved_alarm_faces"] = metrics["self_intersection_faces"]
    if bound:
        metrics["self_intersection_faces"] = 0
    return bool(valid and bound),metrics
