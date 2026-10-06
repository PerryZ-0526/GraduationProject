"""原输入及碎片修复后的候选统一使用绑定全量证据消解未解决报警。"""

import json

from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from exact_embedding_gate import mesh_input_valid_full_embedding, stored_mesh_sha256
from locality_masks import save_obj_fp64
from run_geometry_study import execute
from study_cut_exclusion import input_valid


def audit_input_with_full_embedding(engine, folder, mesh, record):
    """真零面积继续拒绝；合法修复后对象按自己的摘要重新核验，不能继承旧证据。"""
    valid, metrics = input_valid(mesh)
    if valid or not metrics.get("self_intersection_faces", 0) or metrics.get("zero_area_faces", 1) or metrics.get("fp32_zero_area_faces", 1):
        return valid, metrics
    digest = stored_mesh_sha256(mesh)
    checks = record.setdefault("full_input_checks", [])
    previous = next((c for c in checks if c["saved_sha256"] == digest), None)
    if previous is None:
        path = folder / f"input_embedding_{len(checks)}.obj"
        save_obj_fp64(mesh, path)
        remote = engine.remote + "/" + folder.name + "_" + path.name
        engine.sftp.put(str(path), remote)
        if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
            raise ValueError("输入全量审计实际摘要不符")
        run = execute(engine.client, [CHECKER, remote], timeout=120)
        previous = {"saved_sha256": sha256(path), "execution": run}
        if not run["returncode"]:
            previous.update(json.loads(run["stdout"]))
        checks.append(previous)
    return mesh_input_valid_full_embedding(mesh, previous)
