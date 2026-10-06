"""区域面积保护的完整反馈入口，其他碰撞、来源与发布协议保持同一规则。"""
from functools import partial
import run_constrained_feedback as controller
import run_adaptive_feedback as adaptive
from run_collision_protected_feedback import ProtectedEngine
from run_shared_repair_feedback import shared_repair
from run_constrained_batch import RemoteQuality
from locality_diagnostic import source_region,verify_labels
from exact_alarm_contact import mesh_valid_exact_contacts


class AreaGuardEngine(ProtectedEngine):
    def run(self,source,labels,tool,method,folder):
        actual="planar_tangent_protected_areaguard_shared" if method=="boolean" else "expanded_tangent_protected_areaguard_shared" if method=="expanded" else method
        return RemoteQuality.run(self,source,labels,tool,actual,folder)


if __name__=="__main__":
    controller.RemoteQuality=AreaGuardEngine
    controller.VALID_SOURCE_BITS=(1,2,3)
    controller.clean_provenance=shared_repair
    controller.source_region=partial(source_region,allow_shared=True)
    controller.verify_labels=partial(verify_labels,allow_shared=True)
    controller.mesh_valid=mesh_valid_exact_contacts
    adaptive.mesh_valid=mesh_valid_exact_contacts
    controller.audit_candidate=adaptive.audit_adaptive
    controller.main()
