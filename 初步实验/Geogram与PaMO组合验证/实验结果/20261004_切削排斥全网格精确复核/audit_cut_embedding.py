"""对全部冻结输出追加全网格CGAL精确自交审计；不改写已有实验结果。"""

import getpass
import json
from pathlib import Path

import trimesh

from audit_followup_candidate import sha256
from locality_masks import save_obj_fp64
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import execute, save, now

CHECKER = "/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646"


def main():
    output = HERE / "实验结果/20261004_切削排斥全网格精确复核"
    output.mkdir(exist_ok=False)
    config = dict(line.split("=", 1) for line in (HERE.parents[1] / ".env").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    previous = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(output, int(config["CUDA_SSH_PORT"]))
    finally:
        getpass.getpass = previous
        del config
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，先验证检查器再审查全部冻结输出",
              "文档概述": "CGAL EPECK对保存二进制FP64三角面的全量自交检查，区别于有限报警复核",
              "索引目录": ["environment", "tests", "rows"], "tests": [], "rows": [], "status": "running"}
    record = output / "01-全网格精确嵌入审计.json"
    try:
        execute(engine.client, ["mkdir", engine.remote])
        report["environment"] = {"checker_sha256": execute(engine.client, ["sha256sum", CHECKER])["stdout"].split()[0],
            "checker_source_sha256": sha256(HERE / "exact_mesh_audit.cpp"),
            "cgal_version": execute(engine.client, ["dpkg-query", "-W", "libcgal-dev"])["stdout"].strip()}
        (output / "exact_mesh_audit.cpp").write_bytes((HERE / "exact_mesh_audit.cpp").read_bytes())
        (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
        def check(path, index):
            remote = engine.remote + f"/{index}.obj"
            engine.sftp.put(str(path), remote)
            execution = execute(engine.client, [CHECKER, remote], timeout=120)
            if execution["returncode"]:
                return {"path": str(path), "sha256": sha256(path), "execution": execution, "status": "checker_failed"}
            return {"path": str(path), "sha256": sha256(path), "execution": execution,
                    **json.loads(execution["stdout"].strip()), "status": "checked"}
        cube = trimesh.creation.box()
        overlap = trimesh.util.concatenate((cube, trimesh.creation.box(transform=trimesh.transformations.translation_matrix([.25, .25, .25]))))
        disjoint = trimesh.util.concatenate((cube, trimesh.creation.box(transform=trimesh.transformations.translation_matrix([2., 0., 0.]))))
        legal = trimesh.Trimesh([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., -1., 0.]], [[0, 1, 2], [1, 0, 3]], process=False)
        folded = legal.copy()
        folded.vertices[3] = [.5, .5, 0.]
        duplicate = trimesh.Trimesh(legal.vertices, [[0, 1, 2], [2, 1, 0]], process=False)
        fixtures = [("闭合立方体", cube, True, 0), ("分离双实体", disjoint, True, 0),
                    ("交叠双实体", overlap, False, None), ("合法共享边", legal, False, 0),
                    ("共享边折叠重叠", folded, False, None), ("完全重复面", duplicate, False, None)]
        for index, (name, mesh, embedded, pairs) in enumerate(fixtures):
            path = output / f"测试_{name}.obj"
            save_obj_fp64(mesh, path)
            row = check(path, "test_" + str(index))
            passed = row.get("embedded_closed") == embedded and (pairs is None or row.get("self_intersection_pairs") == pairs)
            # 非法接触必须得到具体自交或拓扑拒绝，不能只因开放面而碰巧通过负例。
            if pairs is None:
                passed = passed and (not row.get("topology_valid", True) or row.get("self_intersection_pairs", 0) > 0)
            row.update(case=name, passed=bool(passed))
            report["tests"].append(row)
        save(record, report)
        if not all(row["passed"] for row in report["tests"]):
            report["status"] = "checker_tests_failed_no_certificate_claim"
            save(record, report)
            return
        paths = []
        dev = HERE / "实验结果/20261004_切削排斥半空间开发_整面消融"
        paths.extend(sorted(dev.glob("*.obj")))
        recut = HERE / "实验结果/20261004_质量后重新布尔强对照"
        paths.extend(sorted(recut.glob("*_recut.obj")))
        evaluation = HERE / "实验结果/20261004_切削排斥21几何体独立静态验证"
        for folder in sorted(evaluation.iterdir()):
            if folder.is_dir() and not folder.name.endswith("_shared_full"):
                paths.extend(sorted(folder.glob("*.obj")))
        for index, path in enumerate(paths):
            row = check(path, "mesh_" + str(index))
            report["rows"].append(row)
            save(record, report)
        report.update(status="completed_with_recorded_outcomes", finished_beijing=now(),
                      scope="全量三角面自交检查；须结合闭合链接、方向、面支撑及锚点记录，不能当作整体距离或CCD证书")
        save(record, report)
        print("tests", len(report["tests"]), "meshes", len(report["rows"]),
              "embedded_closed", sum(r.get("embedded_closed", False) for r in report["rows"]), flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
