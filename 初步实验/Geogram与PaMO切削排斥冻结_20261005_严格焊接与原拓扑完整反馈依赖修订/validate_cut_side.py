"""在隔离远端目录编译精确侧分类器，并验证材料内外及包围盒内空腔控制。"""

import argparse
import getpass
import json
from pathlib import Path

import trimesh

from audit_followup_candidate import sha256
from cut_exclusion import supporting_planes, certify_outside_anchor
from cut_side_classifier import ExactCutSide
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import execute, save, now, retrieve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    config = dict(line.split("=", 1) for line in (HERE.parents[1] / ".env").read_text("utf8").splitlines()
                  if line and not line.startswith("#"))
    original = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(args.output, int(config["CUDA_SSH_PORT"]))
    finally:
        getpass.getpass = original
        del config
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，隔离分类器开发验证",
              "文档概述": "完整嵌入检查后分类工具内部锚点，未接入旧连续版本",
              "索引目录": ["environment", "tests", "application"], "status": "running", "tests": [], "application": []}
    record = args.output / "01-精确侧分类器与骨面锚点验证.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("隔离目录已存在")
        for name in ("exact_cut_side.cpp", "cut_side_classifier.py", Path(__file__).name):
            (args.output / name).write_bytes((HERE / name).read_bytes())
        engine.sftp.put(str(HERE / "exact_cut_side.cpp"), engine.remote + "/exact_cut_side.cpp")
        executable = engine.remote + "/exact_cut_side"
        run = execute(engine.client, ["g++", "-O1", "-std=c++17", engine.remote + "/exact_cut_side.cpp",
                                     "-lgmp", "-lmpfr", "-o", executable], engine.remote + "/compile.log", timeout=300)
        retrieve(engine.client, engine.sftp, engine.remote + "/compile.log", args.output / "compile.log")
        if run["returncode"]:
            raise RuntimeError("分类器编译失败，见日志")
        report["environment"] = {"compile": run, "executable": executable,
            "source_sha256": sha256(HERE / "exact_cut_side.cpp"),
            "executable_sha256": execute(engine.client, ["sha256sum", executable])["stdout"].split()[0]}
        save(record, report)
        side = ExactCutSide(engine, executable)
        cube = trimesh.creation.box(extents=[2, 2, 2])
        torus = trimesh.creation.torus(major_radius=2, minor_radius=.5, major_sections=32, minor_sections=16)
        overlap = trimesh.util.concatenate((cube, trimesh.creation.box(extents=[2, 2, 2],
            transform=trimesh.transformations.translation_matrix([.5, .5, .5]))))
        for name, mesh, points, expected in (("立方体内边外", cube, [[0, 0, 0], [1, 0, 0], [2, 0, 0]], [1, 0, -1]),
                ("包围盒内孔洞与实体", torus, [[0, 0, 0], [2, 0, 0]], [-1, 1])):
            result = side.classify(mesh, points)
            report["tests"].append({"case": name, "passed": result["embedded_closed"] and result["sides"] == expected,
                                     "result": result})
        result = side.classify(overlap, [[0, 0, 0]])
        report["tests"].append({"case": "自交实体拒绝分类", "passed": not result["embedded_closed"] and result["sides"] == [], "result": result})
        tool = trimesh.creation.icosphere(subdivisions=1, radius=.2)
        normals, offsets = supporting_planes(tool)
        for name, mesh, expected in (("工具在孔洞内", torus, True), ("工具被材料整包", cube, False)):
            result = side.anchor(mesh, tool, normals, offsets)
            report["tests"].append({"case": name, "passed": result["passed"] == expected,
                "old_bounding_box_anchor": certify_outside_anchor(mesh, tool, normals, offsets), "result": result})
        save(record, report)
        if not all(row["passed"] for row in report["tests"]):
            raise RuntimeError("分类控制未通过，禁止接入候选")
        manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
        for route in manifest["routes"]:
            folder = args.batch / f"{route['id']}_e0_reference"
            path = folder / "validated_reference.obj"
            if not path.exists():
                path = folder / "reference.obj"
            mesh = trimesh.load(path, force="mesh", process=True, validate=True)
            tool = trimesh.load(args.prepared / "inputs" / route["prefix_tools"][0]["mesh"], force="mesh", process=False)
            normals, offsets = supporting_planes(tool)
            result = side.anchor(mesh, tool, normals, offsets)
            report["application"].append({"route": route["id"], "reference_sha256": sha256(path),
                "old_bounding_box_anchor": certify_outside_anchor(mesh, tool, normals, offsets), "result": result})
            save(record, report)
            print(route["id"], "exact_anchor", result["passed"], flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
