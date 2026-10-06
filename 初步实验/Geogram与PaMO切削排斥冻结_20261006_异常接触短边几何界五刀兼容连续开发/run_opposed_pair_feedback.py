"""同来源反向面抵消接入完整反馈，来源审计和GPU求解门槛保持原样。"""
from functools import partial
import run_constrained_feedback as controller
import run_adaptive_feedback as adaptive
from run_cluster_recovered_feedback import ClusterEngine
from independent_reference_recovery import recover_reference
from opposed_facet_cleanup import clean_cancel_opposed
from fragment_pipeline import repair_input
from locality_retriangulate import invalid_faces
from exact_alarm_contact import mesh_valid_exact_contacts
from locality_diagnostic import source_region,verify_labels
from run_constrained_batch import HERE
from audit_followup_candidate import sha256


class PairEngine(ClusterEngine):
    def setup(self):
        info=super().setup()
        names=("opposed_facet_cleanup.py","run_opposed_pair_feedback.py")
        for name in names:
            (self.output/name).write_bytes((HERE/name).read_bytes())
        info["opposed_pair_code_sha256"]={name:sha256(HERE/name) for name in names}
        info["opposed_pair_policy"]="八位焊接后的同来源双面反向链抵消，细精度拓扑保持及完整几何重审；同向或来源冲突拒绝"
        return info


def pair_repair(mesh,bits):
    """先核对反向链，其他小面仍沿用整网格回滚的固定预算修复。"""
    clean,labels,details=clean_cancel_opposed(mesh,bits,allow_shared=True)
    if invalid_faces(clean.vertices,clean.faces).any():
        clean,labels,repair=repair_input(clean,labels,audit=mesh_valid_exact_contacts,
            allow_shared=True,allow_small_incident=True)
        details["fragment_repair"]=repair
    else:
        details["fragment_repair"]={"triggered":False,"reason":"无面积门槛内面"}
    return clean,labels,details


if __name__=="__main__":
    controller.RemoteQuality=PairEngine
    controller.REFERENCE_RECOVERY=recover_reference
    controller.VALID_SOURCE_BITS=(1,2,3)
    controller.clean_provenance=pair_repair
    controller.source_region=partial(source_region,allow_shared=True)
    controller.verify_labels=partial(verify_labels,allow_shared=True)
    controller.mesh_valid=mesh_valid_exact_contacts
    adaptive.mesh_valid=mesh_valid_exact_contacts
    controller.audit_candidate=adaptive.audit_adaptive
    controller.main()
