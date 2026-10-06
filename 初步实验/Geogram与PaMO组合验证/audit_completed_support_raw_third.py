"""只读检验第三刀原始合法GPU网格是否已满足累计工具排斥，不做投影。"""

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
    from face_normal_support_completion import complete_face_support
    from cut_side_classifier import ExactCutSide
    from exact_embedding_gate import mesh_valid_full_embedding
    from geometry_error_distribution import geometry_error_distribution
    root = Path("D:/GraduationProject_切削排斥证据")
    batch = root / "20261005_补充面法向倍率4薄壁三刀真实反馈"
    bp = batch / "01-统一配置完整父反馈记录.json"
    row = json.loads(bp.read_text("utf8"))["rows"][2]
    raw_path = batch / "薄壁_新参数1p4375_交叉_e2_candidate_boolean/raw_full_candidate.obj"
    assert sha256(raw_path) == row["attempt"]["raw_full_output_sha256"] == row["attempt"]["output_sha256"]
    raw = trimesh.load(raw_path, force="mesh", process=False)
    valid, metrics = mesh_valid_full_embedding(raw, row["attempt"]["exact_embedding"])
    assert valid
    prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
    route = next(r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"] if r["id"] == row["route"])
    output = root / "20261005_补充支撑薄壁第三刀原始GPU整面静态核查"
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
        rows = []
        for event in route["cutting_prefix_ids"]:
            item = next(t for t in route["prefix_tools"] if t["event_id"] == event)
            path = prepared / "inputs" / item["mesh"]
            assert sha256(path) == item["sha256"]
            tool = trimesh.load(path, force="mesh", process=False)
            normals, offsets, selected, certificate, completion = complete_face_support(raw, tool)
            anchor = side.anchor(raw, tool, normals, offsets)
            rows.append({"event": event, "tool_sha256": sha256(path), "support": certificate, "completion": completion,
                         "material_side": anchor, "face_support_ids": selected.tolist()})
        reference_path = batch / "薄壁_新参数1p4375_交叉_e2_reference/validated_reference.obj"
        reference = trimesh.load(reference_path, force="mesh", process=False)
        passed = all(r["support"]["passed"] and r["material_side"]["passed"] for r in rows)
        save(output / "01-原始第三刀不投影累计整面认证核查.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，复用已完成GPU原始输出",
            "文档概述": "先检验原始网格是否已合法，不将静态认证改写原维护拒绝", "索引目录": ["rows"],
            "batch_sha256": sha256(bp), "raw_sha256": sha256(raw_path), "rows": rows, "passed": passed,
            "metrics": metrics, "quality": quality_distribution(raw), "distribution": geometry_error_distribution(raw, reference),
            "new_GPU_calls": 0, "vertices_modified": False, "new_publications": 0})
        print([(r["event"], r["support"]["passed"], r["support"]["failed_face_count"], r["material_side"]["passed"]) for r in rows], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
