"""冻结薄壁首刀同源完整阶段观测，远端凭据只读忽略环境文件。"""

import getpass
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, retrieve, save, now, PYTHON


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", choices=("parent", "reference"), required=True)
    args = parser.parse_args()
    project = Path.cwd()
    here = Path('C:\\Users\\24848\\Desktop\\GraduationProject\\初步实验\\Geogram与PaMO切削排斥冻结_20261005_薄壁同源简化预算对照控制')
    root = Path("D:/GraduationProject_切削排斥证据")
    batch = root / "20261005_独立目标预算薄壁三刀完整反馈/薄壁_新参数1p4375_交叉"
    batch_path = batch / "01-统一配置完整父反馈记录.json"
    row = json.loads(batch_path.read_text("utf8"))["rows"][2]
    source = batch / "薄壁_新参数1p4375_交叉_e2_candidate_input/clean_source.obj"
    assert sha(source) == row["attempt"]["audited_source_sha256"]
    output = root / f"20261005_薄壁第三刀同一物理源预算对照_{args.budget}"
    output.mkdir(exist_ok=False)
    frozen = project / f"初步实验/Geogram与PaMO切削排斥冻结_20261005_薄壁第三刀同源预算{args.budget}观测"
    frozen.mkdir(exist_ok=False)
    old = project / "初步实验/Geogram与PaMO切削排斥冻结_20261005_统一最低分辨率256薄壁三刀反馈"
    for name in ("sdf_bias_remesh.py", "normalized_sdf_chain.py", "normalized_working_source_gate.py"):
        shutil.copyfile(old / name, frozen / name)
    shutil.copyfile(here / "thin_full_stage_observation.py", frozen / "thin_full_stage_observation.py")
    worker = (here / "run_fp64_gap_full_worker.py").read_text("utf8")
    marker = "    v, f = model.run(points, faces, ratio=1., min_verts=0)"
    assert worker.count(marker) == 1
    worker = worker.replace(marker, "    from thin_full_stage_observation import install_stage_observation\n    install_stage_observation(out / 'stage_observations', origin)\n" + marker)
    import importlib.util
    spec = importlib.util.spec_from_file_location('reference_budget_control_math', Path(__file__).with_name('simplification_budget_ratio.py'))
    budget_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(budget_module)
    import trimesh
    reference = batch / '薄壁_新参数1p4375_交叉_e2_reference/validated_reference.obj'
    target, ratio = budget_module.target_budget(len(trimesh.load(source, process=False).faces), len(trimesh.load(reference, process=False).faces))
    if args.budget == 'parent':
        ratio = 4.
    worker = worker.replace("ratio=1., min_verts=0", "ratio=" + repr(ratio) + ", min_verts=0")
    worker = worker.replace("01-固定第二刀完整三阶段终态.json", "01-薄壁第三刀同源三阶段观测终态.json")
    (frozen / "thin_stage_worker.py").write_text(worker, "utf8")
    shutil.copyfile(Path(__file__), frozen / Path(__file__).name)
    manifest = [{"file": path.name, "sha256": sha(path)} for path in sorted(frozen.glob("*.py"))]
    save(frozen / "01-执行源码冻结清单.json", manifest)
    cfg = dict(line.split("=", 1) for line in (project / ".env").read_text("utf8").splitlines() if line and not line.startswith("#"))
    getpass.getpass = lambda _: cfg["CUDA_SSH_PASSWORD"]
    os.environ["GPU_SSH_HOST"] = "connect.westb.seetacloud.com"
    engine = RemoteQuality(output, 51667)
    try:
        assert execute(engine.client, ["mkdir", engine.remote])["returncode"] == 0
        # 读取已有静态执行配置以复用原排序扩展绑定，不再次构建或改作者安装。
        with engine.sftp.open("/root/autodl-tmp/graduation_project/thin_minimum_R256_full_20261005_01/inputs.json") as stream:
            inputs = json.loads(stream.read().decode("utf8"))
        inputs.update(source_override={"file": "source.obj", "sha256": sha(source)},
                      origin_override_mm=row["origin_mm"], minimum_sdf_resolution=256)
        save(output / "inputs.json", inputs)
        for path in [frozen / item["file"] for item in manifest] + [output / "inputs.json", source]:
            name = "source.obj" if path == source else path.name
            engine.sftp.put(str(path), engine.remote + "/" + name)
            assert execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0] == sha(path)
        log = engine.remote + "/stdout.log"
        run = execute(engine.client, ["env", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6", PYTHON, engine.remote + "/thin_stage_worker.py"], log, timeout=420)
        retrieve(engine.client, engine.sftp, log, output / "stdout.log")
        save(output / "02-执行终态.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，同一第三刀物理源两档预算实际执行终态",
            "文档概述": "同一第三刀源、原点、排序扩展和三阶段；仅预算不同，阶段读回不用于性能或发布", "索引目录": ["execution"], "execution": run,
            "source_sha256": sha(source), "batch_sha256": sha(batch_path), "snapshot_manifest_sha256": sha(frozen / "01-执行源码冻结清单.json")})
        if run["returncode"]:
            raise RuntimeError("薄壁完整阶段观测未完成，见实际日志")
        for name in ("01-薄壁第三刀同源三阶段观测终态.json", "raw_full_candidate.obj", "isolated_run_fp64.py"):
            retrieve(engine.client, engine.sftp, engine.remote + "/result/" + name, output / name)
        for sub, names in (("stage_observations", ("stage1.obj", "stage2.obj", "stage3.obj", "stage1_centered.npz", "01-薄壁同次完整GPU三阶段保存.json")),
                           ("working_sources", ("01-CUDA初始编码源.obj", "02-CUDA再中心化碰撞源.obj", "03-整理后归一化SDF源.obj", "04-完整求解前实际工作源门控.json"))):
            (output / sub).mkdir()
            for name in names:
                retrieve(engine.client, engine.sftp, engine.remote + "/result/" + sub + "/" + name, output / sub / name)
        stages = json.loads((output / "stage_observations/01-薄壁同次完整GPU三阶段保存.json").read_text("utf8"))
        for item in stages["rows"]:
            assert sha(output / "stage_observations" / item["file"]) == item["sha256"]
        print([(x["stage"], x["faces"], x["volume_mm3"]) for x in stages["rows"]], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
