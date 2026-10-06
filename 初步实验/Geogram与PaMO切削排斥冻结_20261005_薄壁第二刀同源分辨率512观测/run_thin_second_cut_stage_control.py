"""冻结薄壁第二刀同源完整阶段观测，远端凭据只读忽略环境文件。"""

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
    parser.add_argument("--resolution", type=int, choices=(512,), required=True)
    args = parser.parse_args()
    project = Path.cwd()
    here = Path('C:\\Users\\24848\\Desktop\\GraduationProject\\初步实验\\Geogram与PaMO切削排斥冻结_20261005_薄壁同源简化预算对照控制')
    root = Path("D:/GraduationProject_切削排斥证据")
    batch = root / "20261005_薄壁R512完整32刀条件开发/薄壁_00_长序列"
    batch_path = batch / "01-统一配置完整父反馈记录.json"
    row = json.loads(batch_path.read_text("utf8"))["rows"][1]
    source = batch / "薄壁_00_长序列_e1_candidate_input/clean_source.obj"
    assert sha(source) == row["attempt"]["audited_source_sha256"]
    output = root / f"20261005_薄壁第二刀同物理源分辨率对照_R{args.resolution}"
    output.mkdir(exist_ok=False)
    frozen = project / f"初步实验/Geogram与PaMO切削排斥冻结_20261005_薄壁第二刀同源分辨率{args.resolution}观测"
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
    spec = importlib.util.spec_from_file_location('reference_budget_control_math', project / '初步实验/Geogram与PaMO切削排斥冻结_20261005_独立累计目标面预算薄壁反馈/simplification_budget_ratio.py')
    budget_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(budget_module)
    import trimesh
    reference = root / '20261005_薄壁32刀相邻小面完整精确逐步参照生成/薄壁_00_长序列/薄壁_00_长序列_e1_reference/validated_reference.obj'
    target, ratio = budget_module.target_budget(len(trimesh.load(source, process=False).faces), len(trimesh.load(reference, process=False).faces))
    worker = worker.replace("ratio=1., min_verts=0", "ratio=" + repr(ratio) + ", min_verts=0")
    # 隔离worker显式允许两个冻结分辨率，不修改作者安装或其他阶段参数。
    worker = worker.replace("if cfg['minimum_sdf_resolution'] != 256:", "if cfg['minimum_sdf_resolution'] not in (256, 512):")
    worker = worker.replace('本次最低分辨率候选只允许固定256', '本次同源对照仅允许冻结256或512')
    observer_path = frozen / 'thin_full_stage_observation.py'
    observer = observer_path.read_text('utf8')
    observer = observer.replace('"faces": len(mesh.faces),', '"faces": len(mesh.faces), "euler": int(mesh.euler_number), "components": len(mesh.split(only_watertight=False)),')
    observer_path.write_text(observer, 'utf8')
    worker = worker.replace("01-固定第二刀完整三阶段终态.json", "01-薄壁第二刀同源分辨率三阶段观测终态.json")
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
                      origin_override_mm=row["origin_mm"], minimum_sdf_resolution=args.resolution)
        save(output / "inputs.json", inputs)
        for path in [frozen / item["file"] for item in manifest] + [output / "inputs.json", source]:
            name = "source.obj" if path == source else path.name
            engine.sftp.put(str(path), engine.remote + "/" + name)
            assert execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0] == sha(path)
        log = engine.remote + "/stdout.log"
        run = execute(engine.client, ["env", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6", PYTHON, engine.remote + "/thin_stage_worker.py"], log, timeout=420)
        retrieve(engine.client, engine.sftp, log, output / "stdout.log")
        save(output / "02-执行终态.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，同一第二刀物理源两档分辨率实际执行终态",
            "文档概述": "同一第二刀源、原点、排序扩展和三阶段；仅最低SDF分辨率不同，阶段读回不用于性能或发布", "索引目录": ["execution"], "execution": run,
            "source_sha256": sha(source), "batch_sha256": sha(batch_path), "snapshot_manifest_sha256": sha(frozen / "01-执行源码冻结清单.json")})
        if run["returncode"]:
            raise RuntimeError("薄壁完整阶段观测未完成，见实际日志")
        for name in ("01-薄壁第二刀同源分辨率三阶段观测终态.json", "raw_full_candidate.obj", "isolated_run_fp64.py"):
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
