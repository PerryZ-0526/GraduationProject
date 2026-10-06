"""物理面积修复及追加锚点完整反馈，保留原完整计划与所有验收。"""
import hashlib
import sys
from run_constrained_batch import HERE
from run_preserved_geometry_feedback import load_snapshot
from run_anchored_geometry_diagnostic import AnchoredEngine
from preserved_controller_source import replace_once
from physical_repair_operations import SOURCES
from physical_input_repair import SOURCE
from audit_followup_candidate import sha256


def build_entry(original, reference):
    reference = replace_once(reference, "from preserved_input_repair import repair_preserved_input",
        "from physical_input_repair import repair_physical_input as repair_preserved_input")
    # 候选与参照使用同修复机制，参照仍只接收原初态及原工具。
    original = "from physical_feedback_gate import clean_for_backend as physical_clean_for_backend\n"+original
    original = replace_once(original,
        'reference_path.write_text(build_reference((HERE/"independent_reference_recovery.py").read_text(encoding="utf-8")),encoding="utf-8")',
        'reference_path.write_text('+repr(reference)+',encoding="utf-8")')
    return replace_once(original, "    controller.main()", "    controller.clean_for_backend = physical_clean_for_backend\n    controller.main()")


class PhysicalEngine(AnchoredEngine):
    def setup(self):
        info = super().setup()
        names = ("physical_repair_operations.py", "physical_input_repair.py", "physical_feedback_gate.py", "run_physical_geometry_feedback.py")
        paths = []
        for name in names:
            path = self.output/name
            path.write_bytes((HERE/name).read_bytes())
            paths.append(path)
        for name, source in dict(SOURCES, physical_input_repair_snapshot=SOURCE).items():
            path = self.output/(name if name.endswith(".py") else name+".py")
            path.write_text(source, encoding="utf-8")
            paths.append(path)
        # 记录实际加载的入口和生成的参照，避免仅冻结生成器而漏掉执行副本。
        entry = self.output/"physical_feedback_entry.py"
        entry.write_bytes(self.entry_path.read_bytes())
        paths.extend((entry, self.output/"preserved_reference.py", self.output/"preserved_controller.py"))
        info["physical_repair_source_sha256"] = {path.name: sha256(path) for path in paths}
        return info


def main(engine_class=PhysicalEngine):
    # 默认入口保持原物理机制；新机制通过独立类和入口明确冻结。
    identity = hashlib.sha256("\0".join(sys.argv[1:]).encode()).hexdigest()[:12]
    folder = HERE/"实验结果/物理面积入口冻结副本"/identity
    folder.mkdir(parents=True, exist_ok=False)
    source = build_entry((HERE/"run_preserved_geometry_feedback.py").read_text(encoding="utf-8"),
        (HERE/"guarded_reference_recovery.py").read_text(encoding="utf-8"))
    path = folder/"physical_feedback_entry.py"
    path.write_text(source, encoding="utf-8")
    module = load_snapshot("physical_feedback_"+identity, path)
    module.PreservedFeedbackEngine = engine_class
    engine_class.entry_path = path
    module.main()


if __name__ == "__main__":
    main()
