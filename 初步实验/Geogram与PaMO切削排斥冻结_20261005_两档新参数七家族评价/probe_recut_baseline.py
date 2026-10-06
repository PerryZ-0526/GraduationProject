"""强工程对照：原版PaMO完成后重新扣除同一个工具，检查质量和合法性代价。"""

import getpass
import json
from pathlib import Path

import numpy as np
import trimesh

from audit_followup_candidate import sha256, quality_distribution
from geometry_preservation_audit import mesh_valid
from locality_masks import save_obj_fp64
from run_constrained_feedback import global_geometry
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import execute, retrieve, save, now, GEO
from probe_removed_material import tool_clearance


def main():
    prepared = HERE / "实验结果/20261004_局部维护保存帧开发"
    output = HERE / "实验结果/20261004_质量后重新布尔强对照"
    output.mkdir(exist_ok=False)
    config = dict(line.split("=", 1) for line in (HERE.parents[1] / ".env").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    old_prompt = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(output, int(config["CUDA_SSH_PORT"]))
    finally:
        getpass.getpass = old_prompt
        del config
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成；七个CPU后布尔强对照，不运行额外PaMO",
              "文档概述": "原版PaMO后重新扣除工具，采用既有精确CSG与17位输出，评估网格质量代价",
              "索引目录": ["environment", "rows"], "rows": [], "status": "running"}
    record = output / "01-维护后重扣工具对照.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise RuntimeError("对照远端目录无法创建")
        report["environment"] = {"geogram_sha256": execute(engine.client, ["sha256sum", GEO])["stdout"].split()[0],
                                 "script_sha256": sha256(Path(__file__)), "csg_calls_budget": 7}
        (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
        save(record, report)
        for case in ("crossing_e0", "crossing_e1", "crossing_e2", "crossing_e3",
                     "stop_resume_e0", "stop_resume_e1", "stop_resume_e3"):
            full = prepared / f"取回输出/saved_batch_outputs/{case}/r0_full.obj"
            tool_path, source_path = prepared / case / "tool.obj", prepared / case / "source.obj"
            parent_remote, tool_remote, result_remote = [engine.remote + f"/{case}_{name}.obj" for name in ("parent", "tool", "recut")]
            for path, remote in ((full, parent_remote), (tool_path, tool_remote)):
                engine.sftp.put(str(path), remote)
            execution = execute(engine.client, [GEO, parent_remote, tool_remote, result_remote, "--no-simplify"],
                                engine.remote + f"/{case}.log", timeout=120)
            retrieve(engine.client, engine.sftp, engine.remote + f"/{case}.log", output / f"{case}.log")
            row = {"case": case, "execution": execution,
                   "input_hashes": {str(path): sha256(path) for path in (full, tool_path, source_path)}}
            if not execution["returncode"]:
                raw = output / f"{case}_raw_recut.obj"
                retrieve(engine.client, engine.sftp, result_remote, raw)
                # 与原资产加载口径一致，处理精确同坐标冗余索引；原始返回文件始终保留。
                candidate = trimesh.load(raw, force="mesh", process=True, validate=True)
                valid, metrics = mesh_valid(candidate)
                save_obj_fp64(candidate, output / f"{case}_recut.obj")
                tool = trimesh.load(tool_path, force="mesh", process=False)
                points = np.concatenate((candidate.vertices, candidate.triangles_center))
                distance = tool_clearance(points, tool)
                row.update(mesh_valid=valid, metrics=metrics, quality=quality_distribution(candidate),
                           geometry=global_geometry(candidate, trimesh.load(source_path, force="mesh", process=False)),
                           inside_probe_count=int(np.sum(distance < -1e-7)),
                           max_inward_plane_depth_mm=max(0., -float(distance.min())))
            report["rows"].append(row)
            save(record, report)
            print(case, row.get("mesh_valid"), row.get("inside_probe_count"),
                  row.get("quality", {}).get("angle_below_10_deg"), flush=True)
        report["status"] = "completed"
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
