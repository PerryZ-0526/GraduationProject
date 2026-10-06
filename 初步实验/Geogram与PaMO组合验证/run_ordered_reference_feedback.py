"""候选清理不变，独立原初态工具重放采用同样的物理清理顺序。"""
import hashlib
from pathlib import Path
import sys
from audit_followup_candidate import sha256
from run_constrained_batch import HERE
from run_ordered_physical_feedback import OrderedPhysicalEngine
from run_physical_geometry_feedback import build_entry
from run_preserved_geometry_feedback import load_snapshot
from preserved_controller_source import replace_once


def reference_source():
    """只替换参照的抵消清理，不读取维护网格、父链或投影结果。"""
    source=(HERE/'guarded_reference_recovery.py').read_text(encoding='utf-8')
    return replace_once(source,'from opposed_facet_cleanup import clean_cancel_opposed',
        'from ordered_physical_cleanup import ordered_cancel_opposed as clean_cancel_opposed')


class OrderedReferenceEngine(OrderedPhysicalEngine):
    def setup(self):
        info=super().setup()
        path=self.output/'run_ordered_reference_feedback.py'
        path.write_bytes(Path(__file__).read_bytes())
        info['ordered_reference_entry_sha256']=sha256(path)
        info['reference_independence']='仅原初态与累计原工具；物理修复算法与候选共享，不称算法独立真值'
        return info


if __name__=='__main__':
    identity=hashlib.sha256('\0'.join(sys.argv[1:]).encode()).hexdigest()[:12]
    folder=HERE/'实验结果/顺序参照入口冻结副本'/identity
    folder.mkdir(parents=True,exist_ok=False)
    source=build_entry((HERE/'run_preserved_geometry_feedback.py').read_text(encoding='utf-8'),reference_source())
    source=replace_once(source,'from physical_feedback_gate import clean_for_backend as physical_clean_for_backend',
        'from ordered_physical_cleanup import clean_for_backend as physical_clean_for_backend')
    path=folder/'ordered_reference_entry.py'
    path.write_text(source,encoding='utf-8')
    module=load_snapshot('ordered_reference_'+identity,path)
    module.PreservedFeedbackEngine=OrderedReferenceEngine
    OrderedReferenceEngine.entry_path=path
    module.main()
