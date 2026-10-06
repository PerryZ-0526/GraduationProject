"""活动面限定的完整反馈：外部面与点契约成立后才发布，并保留原版分支。"""
import hashlib
import json
from pathlib import Path
import sys
import trimesh
from audit_followup_candidate import sha256
from constrained_quality import fixed_surface_contract
from locality_masks import make_masks
from preserved_feedback_gate import audit_preserved_candidate
from preserved_controller_source import replace_once
from run_active_patch_projection import ActivePatchEngine
from run_constrained_batch import HERE
from run_ordered_reference_feedback import OrderedReferenceEngine,reference_source
from run_physical_geometry_feedback import build_entry
from run_preserved_geometry_feedback import load_snapshot


def audit_active_candidate(engine,source,tool,labels,folder,row):
    row=audit_preserved_candidate(engine,source,tool,labels,folder,row)
    if row['execution']['returncode']:
        return row
    method=row['method']
    candidate_fallback=method=='full' and Path(folder).name.endswith('_candidate_full')
    if method=='full' and not candidate_fallback:
        # 原版独立分支仍按原协议审查，不把候选的固定面约束套到原版。
        return row
    before=trimesh.load(source,process=False);output=trimesh.load(Path(folder)/'candidate.obj',process=False)
    bits=json.loads(Path(labels).read_text(encoding='utf-8'))['operand_bits']
    rings=4 if method.startswith('expanded') or candidate_fallback else 2
    active,fixed=make_masks(before,bits,None,'boolean',rings,allow_shared=True)
    contract=fixed_surface_contract(before,output,active,fixed)
    row['original_activity_external_face_contract']=dict(contract,rings=rings,candidate_full_fallback=candidate_fallback)
    if not contract['passed']:
        row['status']='original_activity_external_face_contract_rejected'
    return row


class ActiveReferenceEngine(OrderedReferenceEngine,ActivePatchEngine):
    def setup(self):
        info=super().setup()
        path=self.output/'run_active_patch_feedback.py';path.write_bytes(Path(__file__).read_bytes())
        info['active_feedback_entry_sha256']=sha256(path)
        info['evaluation_entry_file']=path.name
        info['external_contract']='原活动面外有向面集合与固定点；候选full回退也按四层原活动域检查'
        return info


if __name__=='__main__':
    identity=hashlib.sha256('\0'.join(sys.argv[1:]).encode()).hexdigest()[:12]
    folder=HERE/'实验结果/活动面限定反馈入口冻结副本'/identity
    folder.mkdir(parents=True,exist_ok=False)
    source=build_entry((HERE/'run_preserved_geometry_feedback.py').read_text(encoding='utf-8'),reference_source())
    source=replace_once(source,'from physical_feedback_gate import clean_for_backend as physical_clean_for_backend',
        'from ordered_physical_cleanup import clean_for_backend as physical_clean_for_backend')
    path=folder/'active_reference_entry.py';path.write_text(source,encoding='utf-8')
    module=load_snapshot('active_reference_'+identity,path)
    module.PreservedFeedbackEngine=ActiveReferenceEngine
    module.audit_preserved_candidate=audit_active_candidate
    ActiveReferenceEngine.entry_path=path
    module.main()
