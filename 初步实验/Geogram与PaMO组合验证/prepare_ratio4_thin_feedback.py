"""基于严格复用冻结版本只新增全局倍率4，准备从初态薄壁三刀父反馈。"""

import hashlib
import json
from pathlib import Path
import shutil


def main():
    here = Path(__file__).resolve().parent
    old = here.parent / "Geogram与PaMO切削排斥冻结_20261005_严格无变化复用薄壁三刀反馈"
    output = here.parent / "Geogram与PaMO切削排斥冻结_20261005_倍率4薄壁三刀父反馈"
    output.mkdir(exist_ok=False)
    rows = json.loads((old / "01-执行源码冻结清单.json").read_text("utf8"))
    for item in rows:
        assert hashlib.sha256((old / item["file"]).read_bytes()).hexdigest() == item["sha256"]
        shutil.copyfile(old / item["file"], output / item["file"])
    text = (old / "run_strict_reuse_feedback.py").read_text("utf8")
    text = text.replace('"minimum_sdf_resolution.py"):', '"minimum_sdf_resolution.py", "simplification_budget_ratio.py"):')
    marker = '                install += "from normalized_working_source_gate'
    assert text.count(marker) == 1
    text = text.replace(marker, '                install += "from simplification_budget_ratio import install_simplification_budget_ratio\\ninstall_simplification_budget_ratio(4)\\n"\n' + marker)
    text = text.replace('minimum_SDF_resolution=256, resolution_policy=', 'minimum_SDF_resolution=256, simplification_target_ratio=4, resolution_policy=')
    text = text.replace('isolated_minimum_R256_orientation_fragment_fixed_origin_FP64_SDF_feedback_variant', 'isolated_ratio4_minimum_R256_orientation_fragment_fixed_origin_FP64_SDF_feedback_variant')
    name = "run_ratio4_thin_feedback.py"
    (here / name).write_text(text, "utf8")
    (output / name).write_text(text, "utf8")
    shutil.copyfile(here / "simplification_budget_ratio.py", output / "simplification_budget_ratio.py")
    for filename in (name, "simplification_budget_ratio.py"):
        rows.append({"file": filename, "sha256": hashlib.sha256((output / filename).read_bytes()).hexdigest()})
    (output / "01-执行源码冻结清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf8")
    print(output, flush=True)


if __name__ == "__main__":
    main()
