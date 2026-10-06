"""绑定实际合法基准和失败QP对象，全量计数自交并列有限面号定位。"""

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
import trimesh

from run_reference_cut_feedback import ReferenceCutEngine
from run_geometry_study import execute, save, retrieve, now
from audit_followup_candidate import sha256
from run_constrained_feedback import global_geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    old_path = args.previous / "01-统一配置完整父反馈记录.json"
    old = json.loads(old_path.read_text("utf8"))
    if old["status"] == "running" or old["rows"][0]["status"] != "candidate_rejected":
        raise ValueError("需要已终态的首刀失败记录")
    attempts = old["rows"][0]["attempt"]["cut_exclusion"]["attempts"]
    baseline = min((a for a in attempts if a["exclusion"]["accepted"] and a["mesh_valid"]),
                   key=lambda a: a["geometry"]["probe_max_mm"])
    failed = attempts[-1]
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，定位实际保存QP失败对象",
              "文档概述": "全量计数加前32对定位，不改变旧拒绝", "索引目录": ["rows"],
              "status": "running", "previous_record_sha256": sha256(old_path), "rows": []}
    record = args.output / "01-局部覆盖完整嵌入失败定位.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("诊断目录已存在")
        source = Path(__file__).with_name("diagnose_cut_embedding.cpp")
        engine.sftp.put(str(source), engine.remote + "/diagnosis.cpp")
        report["checker_source_sha256"] = sha256(source)
        build = execute(engine.client, ["g++", "-O1", "-std=c++17", engine.remote + "/diagnosis.cpp",
                   "-lgmp", "-lmpfr", "-o", engine.remote + "/diagnosis"], engine.remote + "/build.log", timeout=300)
        retrieve(engine.client, engine.sftp, engine.remote + "/build.log", args.output / "build.log")
        report["compile"] = build
        if build["returncode"]:
            raise RuntimeError("诊断器编译失败")
        report["checker_sha256"] = execute(engine.client, ["sha256sum", engine.remote + "/diagnosis"])["stdout"].split()[0]
        rid = old["selected_route"]
        ref_path = args.previous / f"{rid}_e0_reference/validated_reference.obj"
        if not ref_path.exists():
            ref_path = ref_path.with_name("reference.obj")
        reference = trimesh.load(ref_path, force="mesh", process=True, validate=True)
        objects = {sha256(path): path for path in args.previous.glob("side_*.obj")}
        for name, attempt in (("合法恢复基准", baseline), ("失败QP实际对象", failed)):
            anchors = attempt["exclusion"]["outside_anchor_certificate"]
            anchor = anchors if isinstance(anchors, dict) else anchors[0]
            digest = anchor["classification"]["saved_mesh_sha256"]
            path = args.output / (name + ".obj")
            shutil.copy2(objects[digest], path)
            if sha256(path) != digest:
                raise ValueError("实际分类对象摘要不符")
            remote = engine.remote + "/" + path.name
            engine.sftp.put(str(path), remote)
            if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != digest:
                raise ValueError("诊断对象上传摘要不符")
            result = execute(engine.client, [engine.remote + "/diagnosis", remote], timeout=120)
            if result["returncode"]:
                raise RuntimeError("实际对象诊断失败")
            checks = json.loads(result["stdout"])
            mesh = trimesh.load(path, force="mesh", process=False)
            summaries = []
            for first, second in checks["intersection_face_ids"]:
                triangles = mesh.triangles[[first, second]]
                summaries.append({"face_ids": [first, second], "vertex_ids": mesh.faces[[first, second]].tolist(),
                                  "area_mm2": mesh.area_faces[[first, second]].tolist(),
                                  "bounds_mm": [triangles.min(axis=(0, 1)).tolist(), triangles.max(axis=(0, 1)).tolist()]})
            row = {"role": name, "saved_sha256": digest, "original_attempt_level": attempt["level"],
                   "checks": checks, "listed_pairs_geometry": summaries, "geometry": global_geometry(mesh, reference)}
            report["rows"].append(row)
            save(record, report)
            print(name, "all_pairs", checks["self_intersection_pairs"], flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
