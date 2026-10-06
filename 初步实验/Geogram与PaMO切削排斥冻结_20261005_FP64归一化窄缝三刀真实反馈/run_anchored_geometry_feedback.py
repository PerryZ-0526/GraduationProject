"""追加固定锚点与完整能量重算接入独立参照完整父反馈。"""
import hashlib
from pathlib import Path
import sys
from run_constrained_batch import HERE
from preserved_controller_source import replace_once


if __name__ == "__main__":
    identity = hashlib.sha256("\0".join(sys.argv[1:]).encode()).hexdigest()[:12]
    folder = HERE/"实验结果/追加锚点入口冻结副本"/identity
    folder.mkdir(parents=True, exist_ok=False)
    original = HERE/"run_guarded_geometry_feedback.py"
    source = original.read_text(encoding="utf-8")
    # 原完整分母、独立参照、固定输入及原版配对保留，只替换候选系统绑定。
    source = "from run_anchored_geometry_diagnostic import AnchoredEngine\n"+source
    source = replace_once(source, "class GuardedEngine(PreservedFeedbackEngine):", "class GuardedEngine(AnchoredEngine):")
    source = replace_once(source, 'names = ("guarded_reference_recovery.py", "run_guarded_geometry_feedback.py")',
        'names = ("guarded_reference_recovery.py", "run_guarded_geometry_feedback.py", "run_anchored_geometry_feedback.py", "run_anchored_geometry_diagnostic.py")')
    path = folder/"anchored_guarded_feedback_entry.py"
    path.write_text(source, encoding="utf-8")
    exec(compile(source, str(path), "exec"), dict(__name__="__main__", __file__=str(path)))
