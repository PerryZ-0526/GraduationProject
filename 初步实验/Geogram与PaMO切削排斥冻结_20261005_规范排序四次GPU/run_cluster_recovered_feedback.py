"""相邻小面固定预算修复、面积保护及独立参照恢复的完整反馈。"""
from functools import partial
import run_constrained_feedback as controller
import run_adaptive_feedback as adaptive
from run_recovered_area_feedback import RecoveredAreaEngine
from independent_reference_recovery import recover_reference
from locality_cleanup import clean_provenance
from locality_retriangulate import invalid_faces
from fragment_pipeline import repair_input
from locality_diagnostic import source_region,verify_labels
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_batch import HERE
from audit_followup_candidate import sha256


class ClusterEngine(RecoveredAreaEngine):
    def setup(self):
        info=super().setup()
        names=("run_cluster_recovered_feedback.py","locality_sliver_collapse.py","fragment_pipeline.py")
        info["small_incident_code_sha256"]={name:sha256(HERE/name) for name in names}
        for name in names:
            (self.output/name).write_bytes((HERE/name).read_bytes())
        info["small_incident_policy"]="极小正面积面有理数支撑方向；链接及1e-8平面预算不变；不新增坏面，每步坏面减少；整网格终态回滚"
        return info


def cluster_repair(mesh,bits):
    """完整修复失败仍返回原清理输入；来源位保持原样，所有帧采用同一规则。"""
    clean,labels,details=clean_provenance(mesh,bits,allow_shared=True)
    if invalid_faces(clean.vertices,clean.faces).any():
        clean,labels,repair=repair_input(clean,labels,audit=mesh_valid_exact_contacts,
            allow_shared=True,allow_small_incident=True)
        details["fragment_repair"]=repair
    else:
        details["fragment_repair"]={"triggered":False,"reason":"无面积门槛内面"}
    return clean,labels,details


if __name__=="__main__":
    controller.RemoteQuality=ClusterEngine
    controller.REFERENCE_RECOVERY=recover_reference
    controller.VALID_SOURCE_BITS=(1,2,3)
    controller.clean_provenance=cluster_repair
    controller.source_region=partial(source_region,allow_shared=True)
    controller.verify_labels=partial(verify_labels,allow_shared=True)
    controller.mesh_valid=mesh_valid_exact_contacts
    adaptive.mesh_valid=mesh_valid_exact_contacts
    controller.audit_candidate=adaptive.audit_adaptive
    controller.main()
