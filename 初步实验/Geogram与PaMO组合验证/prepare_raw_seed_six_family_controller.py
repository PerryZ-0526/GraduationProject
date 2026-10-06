"""继续同一原始目标提案版本的六家族，冻结完整18事件分母。"""

import hashlib
import json
from pathlib import Path
import shutil


def main():
    here = Path(__file__).resolve().parent
    old = here.parent / "Geogram与PaMO切削排斥冻结_20261005_补充支撑倍率4六家族执行控制"
    text = (old / "run_completed_support_six_family_controller.py").read_text("utf8")
    text = text.replace("Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈", "Geogram与PaMO切削排斥冻结_20261005_原始顶点局部提案薄壁反馈")
    text = text.replace("20261005_补充面法向倍率4六家族18事件完整开发", "20261005_原始顶点提案同版六家族18事件完整开发")
    text = text.replace("Geogram与PaMO切削排斥冻结_20261005_补充支撑独立保存复审", "Geogram与PaMO切削排斥冻结_20261005_原始顶点提案独立保存复审")
    text = text.replace("run_completed_support_feedback.py", "run_raw_seed_feedback.py")
    text = text.replace("audit_completed_support_outputs.py", "audit_raw_seed_outputs.py")
    text = text.replace("补充支撑方向、倍率4及最低R256数值快照", "原始顶点额外提案、补充支撑方向、倍率4及最低R256数值快照")
    output = here.parent / "Geogram与PaMO切削排斥冻结_20261005_原始顶点提案六家族执行控制"
    output.mkdir(exist_ok=False)
    (output / "run_raw_seed_six_family_controller.py").write_text(text, "utf8")
    shutil.copyfile(old / "frozen_feedback_child.py", output / "frozen_feedback_child.py")
    rows = [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(output.glob("*.py"))]
    (output / "01-执行源码冻结清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf8")
    print(output, flush=True)


if __name__ == "__main__":
    main()
