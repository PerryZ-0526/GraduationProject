"""第三刀同一GPU对象只投影违反排斥的原顶点，不先把全网格拉向参照。"""

import getpass
import json
import os
from pathlib import Path
import sys


def main():
    project = Path.cwd()
    snapshot = project / "初步实验/Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈"
    sys.path.insert(0, str(snapshot))
    import trimesh
    from run_constrained_batch import RemoteQuality
    from run_geometry_study import execute, save, now
    from audit_followup_candidate import sha256, quality_distribution
    from cut_side_classifier import ExactCutSide
    from cut_exclusion import repair_cut_exclusion_many
    from exact_embedding_gate import mesh_valid_full_embedding
    from geometry_error_distribution import geometry_error_distribution
    from locality_masks import save_obj_fp64
    root = Path("D:/GraduationProject_切削排斥证据")
    batch = root / "20261005_补充面法向倍率4薄壁三刀真实反馈"
    bp = batch / "01-统一配置完整父反馈记录.json"
    row = json.loads(bp.read_text("utf8"))["rows"][2]
    raw_path = batch / "薄壁_新参数1p4375_交叉_e2_candidate_boolean/raw_full_candidate.obj"
    assert sha256(raw_path) == row["attempt"]["raw_full_output_sha256"]
    raw = trimesh.load(raw_path, force="mesh", process=False)
    prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
    route = next(r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"] if r["id"] == row["route"])
    tools, tool_bindings = [], []
    for item in route["prefix_tools"]:
        path = prepared / "inputs" / item["mesh"]
        assert sha256(path) == item["sha256"]
        tools.append(trimesh.load(path, force="mesh", process=False))
        tool_bindings.append(sha256(path))
    output = root / "20261005_薄壁第三刀原始顶点目标局部投影同源对照"
    output.mkdir(exist_ok=False)
    cfg = dict(line.split("=", 1) for line in (project / ".env").read_text("utf8").splitlines() if line and not line.startswith("#"))
    getpass.getpass = lambda _: cfg["CUDA_SSH_PASSWORD"]
    os.environ["GPU_SSH_HOST"] = "connect.westb.seetacloud.com"
    engine = RemoteQuality(output, 51667)
    try:
        assert execute(engine.client, ["mkdir", engine.remote])["returncode"] == 0
        validation = json.loads((project / "初步实验/Geogram与PaMO组合验证/实验结果/20261004_切削排斥精确材料侧分类开发/01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))["environment"]
        assert execute(engine.client, ["sha256sum", validation["executable"]])["stdout"].split()[0] == validation["executable_sha256"]
        side = ExactCutSide(engine, validation["executable"])
        mesh, details = repair_cut_exclusion_many(raw, tools, budget_mm=.1, anchor_classifier=side.anchor)
        saved = output / "01-原始目标投影候选.obj"
        save_obj_fp64(mesh, saved)
        loaded = trimesh.load(saved, force="mesh", process=False)
        classification = side.classify(loaded, tools[0].vertices.mean(axis=0).reshape(1, 3))
        valid, metrics = mesh_valid_full_embedding(loaded, classification)
        reference = trimesh.load(batch / "薄壁_新参数1p4375_交叉_e2_reference/validated_reference.obj", force="mesh", process=False)
        save(output / "02-原始目标与参照种子同GPU对照核查.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，原始顶点目标单一提案",
            "文档概述": "同一已完成GPU对象，不做全局最近点恢复，不改原参考种子拒绝或发布状态", "索引目录": ["projection", "audit"],
            "raw_sha256": sha256(raw_path), "batch_sha256": sha256(bp), "cumulative_tools_sha256": tool_bindings,
            "projection": details, "audit": {"valid_embedding": valid, "metrics": metrics, "classification": classification,
                "saved_sha256": sha256(saved), "quality": quality_distribution(loaded), "distribution": geometry_error_distribution(loaded, reference)},
            "new_GPU_calls": 0, "new_publications": 0, "passed": bool(details["accepted"] and valid)})
        print({"projection_accepted": details["accepted"], "embedding_valid": valid, "reason": details.get("reason"),
               "moved_vertices": details["moved_vertices"], "max_displacement_mm": details.get("max_displacement_mm")}, flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
