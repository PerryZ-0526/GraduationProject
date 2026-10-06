"""只改变作者简化目标面倍率，三阶段保持，冻结1/2/4同源对照入口。"""

import hashlib
import json
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    text = (here / "run_thin_full_stage_observation.py").read_text("utf8")
    text = text.replace('import getpass\n', 'import getpass\nimport argparse\n', 1)
    text = text.replace('    project = Path.cwd()', '    parser = argparse.ArgumentParser(description=__doc__)\n    parser.add_argument("--ratio", type=int, choices=(1, 2, 4), required=True)\n    args = parser.parse_args()\n    project = Path.cwd()', 1)
    text = text.replace('"20261005_薄壁首刀同次完整GPU三阶段定位"', 'f"20261005_薄壁首刀同源简化预算对照_ratio{args.ratio}"')
    text = text.replace('"初步实验/Geogram与PaMO切削排斥冻结_20261005_薄壁首刀完整阶段观测"', 'f"初步实验/Geogram与PaMO切削排斥冻结_20261005_薄壁同源预算{args.ratio}观测"')
    text = text.replace('    worker = worker.replace("01-固定第二刀', '    worker = worker.replace("ratio=1., min_verts=0", "ratio=" + str(args.ratio) + "., min_verts=0")\n    worker = worker.replace("01-固定第二刀', 1)
    text = text.replace('"stage1.obj", "stage2.obj", "stage3.obj", "01-薄壁同次完整GPU三阶段保存.json"', '"stage1.obj", "stage2.obj", "stage3.obj", "stage1_centered.npz", "01-薄壁同次完整GPU三阶段保存.json"')
    name = "run_thin_simplification_budget_control.py"
    (here / name).write_text(text, "utf8")
    control = here.parent / "Geogram与PaMO切削排斥冻结_20261005_薄壁同源简化预算对照控制"
    control.mkdir(exist_ok=False)
    for filename, content in ((name, text), ("thin_full_stage_observation.py", (here / "thin_full_stage_observation.py").read_text("utf8")),
                              ("run_fp64_gap_full_worker.py", (here / "run_fp64_gap_full_worker.py").read_text("utf8"))):
        (control / filename).write_text(content, "utf8")
    # 运行器的非数值依赖由原同级快照导入，避免另一聊天改动共享文件影响执行。
    old = here.parent / "Geogram与PaMO切削排斥冻结_20261005_严格无变化复用薄壁三刀反馈"
    import shutil
    for row in json.loads((old / "01-执行源码冻结清单.json").read_text("utf8")):
        if not (control / row["file"]).exists():
            assert hashlib.sha256((old / row["file"]).read_bytes()).hexdigest() == row["sha256"]
            shutil.copyfile(old / row["file"], control / row["file"])
    rows = [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(control.iterdir()) if p.is_file() and p.name != "01-执行源码冻结清单.json"]
    (control / "01-执行源码冻结清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf8")
    print(control, flush=True)


if __name__ == "__main__":
    main()
