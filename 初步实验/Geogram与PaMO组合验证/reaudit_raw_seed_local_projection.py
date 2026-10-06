"""重新加载两点修正输出，对原冻结支撑及三个材料侧锚点独立复审。"""

import getpass
import json
import os
from pathlib import Path
import sys


def main():
    project = Path.cwd()
    sys.path.insert(0, str(project / "初步实验/Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈"))
    import numpy as np
    import trimesh
    from run_constrained_batch import RemoteQuality
    from run_geometry_study import execute, save, now
    from audit_followup_candidate import sha256
    from cut_exclusion import supporting_planes, certify_face_support
    from cut_side_classifier import ExactCutSide
    from exact_embedding_gate import mesh_valid_full_embedding
    root = Path("D:/GraduationProject_切削排斥证据")
    original = root / "20261005_薄壁第三刀原始顶点目标局部投影同源对照"
    op = original / "02-原始目标与参照种子同GPU对照核查.json"
    data = json.loads(op.read_text("utf8"))
    path = original / "01-原始目标投影候选.obj"
    assert sha256(path) == data["audit"]["saved_sha256"]
    mesh = trimesh.load(path, force="mesh", process=False)
    prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
    route = next(r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"] if r["id"].startswith("薄壁_"))
    paths = [prepared / "inputs" / t["mesh"] for t in route["prefix_tools"]]
    assert [sha256(p) for p in paths] == data["cumulative_tools_sha256"]
    tools = [trimesh.load(p, force="mesh", process=False) for p in paths]
    planes = [supporting_planes(t) for t in tools]
    normals, offsets = np.concatenate([n for n, _ in planes]), np.concatenate([b for _, b in planes])
    certificates = [certify_face_support(mesh, normals, offsets, choice) for choice in data["projection"]["frozen_face_support_ids"]]
    output = root / "20261005_薄壁第三刀两点修正保存独立复审"
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
        anchors = [side.anchor(mesh, tool, n, b) for tool, (n, b) in zip(tools, planes)]
        valid, metrics = mesh_valid_full_embedding(mesh, anchors[0]["classification"])
        raw = trimesh.load(root / "20261005_补充面法向倍率4薄壁三刀真实反馈/薄壁_新参数1p4375_交叉_e2_candidate_boolean/raw_full_candidate.obj", force="mesh", process=False)
        faces_same = np.array_equal(mesh.faces, raw.faces)
        moved = np.flatnonzero(np.any(mesh.vertices != raw.vertices, axis=1))
        passed = bool(valid and faces_same and all(c["passed"] for c in certificates + anchors))
        assert passed and len(moved) == 2
        save(output / "01-两点修正保存网格完整独立复审.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，重新加载同一保存候选复审",
            "文档概述": "冻结整面支撑独立复核、重新材料侧分类及完整嵌入；仍为静态开发",
            "索引目录": ["certificates", "anchors"], "projection_record_sha256": sha256(op), "saved_sha256": sha256(path),
            "certificates": certificates, "anchors": anchors, "metrics": metrics, "faces_same": faces_same,
            "moved_vertex_ids": moved.tolist(), "passed": passed, "new_GPU_calls": 0, "new_publications": 0})
        print("two_vertex_projection_saved_reaudit_passed", flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
