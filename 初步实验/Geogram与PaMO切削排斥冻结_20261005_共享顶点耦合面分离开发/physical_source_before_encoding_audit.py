"""物理FP64源先验与实际编码工作源门控分开，不改输出验收。"""

import json
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from locality_masks import save_obj_fp64
from positive_area_input import positive_area_input
from run_geometry_study import execute


def audit_physical_source(engine, folder, mesh, record):
    if execute(engine.client, ["sha256sum", CHECKER])["stdout"].split()[0] != "0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3":
        raise ValueError("物理FP64源精确检查器摘要改变")
    _, metrics = positive_area_input(mesh)
    # 世界坐标FP32仅记录风险；真正执行的编码源在完整GPU入口另作三重门控。
    metrics.update(input_encoding_policy="world_FP64_physical_source_then_actual_CUDA_working_source_gates",
                   world_FP32_risk_faces=metrics.get("fp32_zero_area_faces"),
                   actual_encoded_source_verification_pending=True)
    path = folder / ("physical_source_" + str(len(record.get("physical_source_checks", []))) + ".obj")
    save_obj_fp64(mesh, path)
    remote = engine.remote + "/" + folder.name + "_" + path.name
    engine.sftp.put(str(path), remote)
    if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
        raise ValueError("物理FP64源实际对象摘要不同")
    run = execute(engine.client, [CHECKER, remote], timeout=120)
    certificate = {"saved_sha256": sha256(path), "execution": run}
    if not run["returncode"]:
        certificate.update(json.loads(run["stdout"]))
    record.setdefault("physical_source_checks", []).append(certificate)
    metrics["physical_FP64_full_embedding"] = certificate.get("embedded_closed", False)
    arithmetic = metrics.get("area_arithmetic", [])
    positive = bool(arithmetic and arithmetic[0]["dtype"] == "float64" and
                    arithmetic[0]["zero_faces"] == 0 and arithmetic[0]["nonfinite_areas"] == 0)
    valid = certificate.get("embedded_closed", False) and positive and all(metrics.get(key, False) for key in
             ("finite", "watertight", "winding_consistent", "vertex_manifold_closed"))
    return bool(valid), metrics
