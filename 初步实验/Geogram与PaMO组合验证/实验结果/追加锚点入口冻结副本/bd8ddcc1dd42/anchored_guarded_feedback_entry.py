from run_anchored_geometry_diagnostic import AnchoredEngine
"""固定几何候选配合逐步保护的独立参照，执行原完整范围新批次。"""
import hashlib
from pathlib import Path
import sys
from audit_followup_candidate import sha256
from preserved_controller_source import replace_once
from run_constrained_batch import HERE
from run_preserved_geometry_feedback import load_snapshot, PreservedFeedbackEngine


if __name__ == "__main__":
    identity = hashlib.sha256("\0".join(sys.argv[1:]).encode()).hexdigest()[:12]
    folder = HERE/"实验结果/逐步参照入口冻结副本"/identity
    folder.mkdir(parents=True, exist_ok=False)
    original = HERE/"run_preserved_geometry_feedback.py"
    source = original.read_text(encoding="utf-8")
    # 保留同一候选后端、父链和完整分母，仅替换独立参照恢复源码。
    source = replace_once(source,
        'reference_path.write_text(build_reference((HERE/"independent_reference_recovery.py").read_text(encoding="utf-8")),encoding="utf-8")',
        'reference_path.write_text((HERE/"guarded_reference_recovery.py").read_text(encoding="utf-8"),encoding="utf-8")')
    snapshot = folder/"guarded_feedback_entry.py"
    snapshot.write_text(source, encoding="utf-8")
    module = load_snapshot("guarded_feedback_"+identity, snapshot)

    class GuardedEngine(AnchoredEngine):
        def setup(self):
            info = super().setup()
            names = ("guarded_reference_recovery.py", "run_guarded_geometry_feedback.py", "run_anchored_geometry_feedback.py", "run_anchored_geometry_diagnostic.py")
            for name in names:
                (self.output/name).write_bytes((HERE/name).read_bytes())
            (self.output/snapshot.name).write_bytes(snapshot.read_bytes())
            info.update(guarded_reference_sha256=sha256(HERE/names[0]),
                guarded_entry_sha256=sha256(snapshot), original_entry_sha256=sha256(original))
            return info

    module.PreservedFeedbackEngine = GuardedEngine
    module.main()
