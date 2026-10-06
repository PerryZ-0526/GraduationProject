"""严格无变化事件只复用保存父网格，并重新认证全部累计凸工具。"""

import json
from pathlib import Path
import shutil

import trimesh

from face_normal_support_completion import complete_face_support
from exact_oriented_surface_identity import exact_oriented_surface_identity
from cut_exclusion import supporting_planes, face_separators, certify_face_support
from exact_embedding_gate import mesh_valid_full_embedding, stored_mesh_sha256
from audit_cut_embedding import CHECKER
from audit_followup_candidate import sha256, quality_distribution
from run_geometry_study import execute, save, now


def try_strict_no_change_reuse(engine, parent_path, source_path, labels_path, tools_paths, folder):
    parent = trimesh.load(parent_path, force="mesh", process=False)
    source = trimesh.load(source_path, force="mesh", process=False)
    bits = json.loads(Path(labels_path).read_text("utf8"))["operand_bits"]
    identity = exact_oriented_surface_identity(parent, source, bits)
    if not identity["same"]:
        return None
    # 文件原样复制，复用没有坐标移动；新的工具历史仍须逐个重新审查。
    folder = Path(folder)
    folder.mkdir(exist_ok=False)
    path = folder / "candidate.obj"
    shutil.copyfile(parent_path, path)
    canonical = folder / "saved_for_embedding_audit.obj"
    from locality_masks import save_obj_fp64
    save_obj_fp64(parent, canonical)
    remote = engine.remote + "/strict_reuse_embedding.obj"
    engine.sftp.put(str(canonical), remote)
    if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(canonical):
        raise ValueError("复用保存对象远端摘要不匹配")
    run = execute(engine.client, [CHECKER, remote], timeout=120)
    embedding = {"execution": run, "saved_sha256": sha256(canonical)}
    if not run["returncode"]:
        embedding.update(json.loads(run["stdout"]))
    valid, metrics = mesh_valid_full_embedding(parent, embedding)
    certificates = []
    for tool_path in tools_paths:
        tool = trimesh.load(tool_path, force="mesh", process=False)
        # 新方向须精确包含整个工具，再用于整面证明，物理顶点保持。
        normals, offsets, selected, support, completion = complete_face_support(parent, tool)
        anchor = engine.side.anchor(parent, tool, normals, offsets)
        certificates.append({"tool_sha256": sha256(tool_path), "face_support_ids": selected.tolist(),
                             "face_support": support, "material_side": anchor, "support_completion": completion})
    same_topology = parent.euler_number == source.euler_number and len(parent.split(only_watertight=False)) == len(source.split(only_watertight=False))
    passed = valid and same_topology and bool(certificates) and all(
        item["face_support"]["passed"] and item["material_side"]["passed"] for item in certificates)
    result = {"status": "accepted_geometry_observation" if passed else "strict_reuse_legality_rejected",
              "execution_role": "strict_no_change_reuse", "full_GPU_calls": 0,
              "identity": identity, "parent_sha256": sha256(parent_path), "output_sha256": sha256(path),
              "audited_source_sha256": sha256(source_path), "audited_labels_sha256": sha256(labels_path),
              "canonical_mesh_sha256": stored_mesh_sha256(parent), "exact_embedding": embedding,
              "output_metrics": metrics, "same_topology_as_source": same_topology,
              "cumulative_tools": certificates, "quality": quality_distribution(parent),
              "audit_time_beijing": now(), "continuous_geometry_certified": False}
    save(folder / "01-严格无变化复用与累计工具复审.json", result)
    return result
