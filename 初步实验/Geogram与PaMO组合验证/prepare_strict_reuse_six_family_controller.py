"""同一严格复用数值版本继续六家族；薄壁已完成，不重新执行。"""

import hashlib
import json
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    text = (here / "run_fixed_origin_six_family_controller.py").read_text("utf8")
    text = text.replace("Geogram与PaMO切削排斥冻结_20261005_方向修复固定原点六家族验证", "Geogram与PaMO切削排斥冻结_20261005_严格无变化复用薄壁三刀反馈")
    text = text.replace("startswith('窄缝_')", "startswith('薄壁_')")
    text = text.replace("20261005_固定原点六家族18事件完整开发", "20261005_严格复用同版六家族18事件完整开发")
    text = text.replace("Geogram与PaMO切削排斥冻结_20261005_分布观察控制与复审", "Geogram与PaMO切削排斥冻结_20261005_严格复用保存独立复审")
    text = text.replace("run_valid_reference_feedback.py", "run_strict_reuse_feedback.py")
    text = text.replace("audit_distribution_observation_outputs.py", "audit_strict_reuse_outputs.py")
    text = text.replace("已见六家族开发，不含重复窄缝，数值算法与409快照一致，补合法参照状态处理", "已见六家族开发，不含已完成薄壁，与本轮薄壁相同严格复用及最低R256数值快照")
    entry = here / "run_strict_reuse_six_family_controller.py"
    entry.write_text(text, "utf8")
    output = here.parent / "Geogram与PaMO切削排斥冻结_20261005_严格复用六家族执行控制"
    output.mkdir(exist_ok=False)
    for name, content in ((entry.name, text), ("frozen_feedback_child.py", (here / "frozen_feedback_child.py").read_text("utf8"))):
        (output / name).write_text(content, "utf8")
    rows = [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(output.glob("*.py"))]
    (output / "01-执行源码冻结清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf8")
    print(output, flush=True)


if __name__ == "__main__":
    main()
