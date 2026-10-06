"""第二版保留输入的强工程对照：共享原版维护输出，再用Geogram重扣同一工具。"""

import getpass
import json
from pathlib import Path

import numpy as np
import trimesh

from audit_followup_candidate import sha256, quality_distribution
from exact_alarm_contact import mesh_valid_exact_contacts
from audit_cut_embedding import CHECKER
from locality_masks import save_obj_fp64
from run_constrained_feedback import global_geometry
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import execute, retrieve, save, now, GEO
from probe_removed_material import tool_clearance


def main():
    study = HERE / "实验结果/20261004_自适应切削排斥28几何体独立静态验证"
    assets = HERE.parent / "可复用磨削测试集/独立切削约束输入_v2"
    output = HERE / "实验结果/20261004_自适应切削排斥28几何体重扣强对照"
    output.mkdir(exist_ok=False)
    manifest = json.loads((assets / "01-完整范围冻结清单.json").read_text("utf8"))
    routes = {x["id"]: x for x in manifest["routes"]}
    previous = json.loads((study / "02-独立静态执行与审计.json").read_text("utf8"))
    config = dict(line.split("=", 1) for line in (HERE.parents[1] / ".env").read_text("utf8").splitlines()
                  if line and not line.startswith("#"))
    prompt = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(output, int(config["CUDA_SSH_PORT"]))
    finally:
        getpass.getpass = prompt
        del config
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成；结果已见后的补充强对照，不调候选参数",
              "文档概述": "28个共享原版输出，各一次重新求差集，无额外PaMO；全网格精确自交及既有距离门槛",
              "索引目录": ["environment", "rows"], "rows": [], "status": "running"}
    record = output / "01-重扣强对照执行与审计.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise RuntimeError("远端对照目录无法创建")
        (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
        report["environment"] = {"script_sha256": sha256(Path(__file__)), "csg_calls_budget": 28,
                                 "previous_study_sha256": sha256(study / "02-独立静态执行与审计.json"),
                                 "geogram_sha256": execute(engine.client, ["sha256sum", GEO])["stdout"].split()[0],
                                 "checker_sha256": execute(engine.client, ["sha256sum", CHECKER])["stdout"].split()[0]}
        save(record, report)
        for item in previous["rows"]:
            rid = item["route"]
            full, source = study / rid / "full.obj", study / rid / "source.obj"
            tool_path = assets / "inputs" / routes[rid]["prefix_tools"][0]["mesh"]
            remote_full, remote_tool, remote_out = [engine.remote + f"/{rid}_{name}.obj" for name in ("full", "tool", "recut")]
            engine.sftp.put(str(full), remote_full)
            engine.sftp.put(str(tool_path), remote_tool)
            execution = execute(engine.client, [GEO, remote_full, remote_tool, remote_out, "--no-simplify"],
                                engine.remote + f"/{rid}.log", timeout=120)
            retrieve(engine.client, engine.sftp, engine.remote + f"/{rid}.log", output / f"{rid}.log")
            row = {"route": rid, "execution": execution, "input_hashes": {str(p): sha256(p) for p in (full, source, tool_path)}}
            if not execution["returncode"]:
                raw = output / f"{rid}_raw_recut.obj"
                retrieve(engine.client, engine.sftp, remote_out, raw)
                # 保留原始I/O，再处理同坐标冗余索引；输出仍须经过完整审计。
                mesh = trimesh.load(raw, force="mesh", process=True, validate=True)
                cleaned = output / f"{rid}_recut.obj"
                save_obj_fp64(mesh, cleaned)
                valid, checks = mesh_valid_exact_contacts(mesh)
                geometry = global_geometry(mesh, trimesh.load(source, force="mesh", process=False))
                tool = trimesh.load(tool_path, force="mesh", process=False)
                values = tool_clearance(np.concatenate((mesh.vertices, mesh.triangles_center)), tool)
                remote_clean = engine.remote + f"/{rid}_cleaned.obj"
                engine.sftp.put(str(cleaned), remote_clean)
                exact_run = execute(engine.client, [CHECKER, remote_clean])
                exact = json.loads(exact_run["stdout"].strip()) if not exact_run["returncode"] else {"execution": exact_run}
                same_topology = mesh.euler_number == item["input_checks"]["euler_number"] and len(mesh.split(only_watertight=False)) == item["input_checks"]["components"]
                row.update(mesh_valid=valid, checks=checks, geometry=geometry, quality=quality_distribution(mesh),
                           exact_embedding=exact, same_topology=same_topology, output_sha256=sha256(cleaned),
                           inside_probe_count=int(np.sum(values < -1e-7)), max_inward_plane_depth_mm=max(0., -float(values.min())),
                           accepted=bool(valid and same_topology and geometry["probe_max_mm"] <= .1 and exact.get("embedded_closed", False)))
            report["rows"].append(row)
            save(record, report)
            print(rid, row.get("accepted"), row.get("inside_probe_count"), flush=True)
        report.update(status="completed_with_recorded_outcomes", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
