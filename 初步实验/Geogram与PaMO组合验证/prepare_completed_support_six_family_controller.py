"""同一补充支撑倍率4版本继续六家族，不重复已完成薄壁。"""

import hashlib
import json
from pathlib import Path
import shutil


def main():
    here = Path(__file__).resolve().parent
    old = here.parent / "Geogram与PaMO切削排斥冻结_20261005_严格复用六家族执行控制"
    for row in json.loads((old / "01-执行源码冻结清单.json").read_text("utf8")):
        assert hashlib.sha256((old / row["file"]).read_bytes()).hexdigest() == row["sha256"]
    text = (old / "run_strict_reuse_six_family_controller.py").read_text("utf8")
    text = text.replace("Geogram与PaMO切削排斥冻结_20261005_严格无变化复用薄壁三刀反馈", "Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈")
    text = text.replace("20261005_严格复用同版六家族18事件完整开发", "20261005_补充面法向倍率4六家族18事件完整开发")
    text = text.replace("Geogram与PaMO切削排斥冻结_20261005_严格复用保存独立复审", "Geogram与PaMO切削排斥冻结_20261005_补充支撑独立保存复审")
    text = text.replace("run_strict_reuse_feedback.py", "run_completed_support_feedback.py")
    text = text.replace("audit_strict_reuse_outputs.py", "audit_completed_support_outputs.py")
    text = text.replace("与本轮薄壁相同严格复用及最低R256数值快照", "与本轮薄壁相同补充支撑方向、倍率4及最低R256数值快照")
    output = here.parent / "Geogram与PaMO切削排斥冻结_20261005_补充支撑倍率4六家族执行控制"
    output.mkdir(exist_ok=False)
    (output / "run_completed_support_six_family_controller.py").write_text(text, "utf8")
    shutil.copyfile(old / "frozen_feedback_child.py", output / "frozen_feedback_child.py")
    rows = [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(output.glob("*.py"))]
    (output / "01-执行源码冻结清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf8")
    print(output, flush=True)


if __name__ == "__main__":
    main()
