"""独立新版本完整反馈入口，保留旧冻结方法及所有后端门控。"""
import hashlib
import sys
from run_constrained_batch import HERE
from audit_followup_candidate import sha256
from run_initial_encoding_feedback import InitialPhysicalEngine
from run_physical_geometry_feedback import build_entry
from run_preserved_geometry_feedback import load_snapshot
from preserved_controller_source import replace_once
from ordered_physical_cleanup import SOURCE


class OrderedPhysicalEngine(InitialPhysicalEngine):
    def setup(self):
        info = super().setup()
        paths = []
        for name in ('ordered_physical_cleanup.py', 'run_ordered_physical_feedback.py'):
            path = self.output/name
            path.write_bytes((HERE/name).read_bytes())
            paths.append(path)
        snapshot = self.output/'ordered_physical_cleanup_snapshot.py'
        snapshot.write_text(SOURCE, encoding='utf-8')
        paths.append(snapshot)
        info['ordered_cleanup_source_sha256'] = {path.name:sha256(path) for path in paths}
        return info


if __name__ == '__main__':
    identity = hashlib.sha256('\0'.join(sys.argv[1:]).encode()).hexdigest()[:12]
    folder = HERE/'实验结果/顺序修复入口冻结副本'/identity
    folder.mkdir(parents=True, exist_ok=False)
    source = build_entry((HERE/'run_preserved_geometry_feedback.py').read_text(encoding='utf-8'),
        (HERE/'guarded_reference_recovery.py').read_text(encoding='utf-8'))
    source = replace_once(source,
        'from physical_feedback_gate import clean_for_backend as physical_clean_for_backend',
        'from ordered_physical_cleanup import clean_for_backend as physical_clean_for_backend')
    path = folder/'ordered_feedback_entry.py'
    path.write_text(source, encoding='utf-8')
    module = load_snapshot('ordered_feedback_'+identity, path)
    module.PreservedFeedbackEngine = OrderedPhysicalEngine
    OrderedPhysicalEngine.entry_path = path
    module.main()
