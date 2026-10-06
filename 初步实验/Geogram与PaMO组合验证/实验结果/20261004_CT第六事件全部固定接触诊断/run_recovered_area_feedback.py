"""面积保护与独立参照恢复的完整反馈入口，保留主参照失败与全部回退代价。"""
from functools import partial
import run_constrained_feedback as controller
import run_adaptive_feedback as adaptive
from run_patch_area_guard_feedback import AreaGuardEngine
from run_shared_repair_feedback import shared_repair
from locality_diagnostic import source_region,verify_labels
from exact_alarm_contact import mesh_valid_exact_contacts
from independent_reference_recovery import recover_reference
from run_constrained_batch import HERE
from audit_followup_candidate import sha256


class RecoveredAreaEngine(AreaGuardEngine):
    def setup(self):
        info=super().setup()
        info["reference_recovery_policy"]="原初态截至当前工具顺序重放；修复探针预算1e-7毫米；包含事件哈希复用"
        # 本机恢复及控制器代码也保存快照，不能只冻结远端GPU worker。
        names=("run_recovered_area_feedback.py","independent_reference_recovery.py","recover_public_reference.py",
               "run_constrained_feedback.py","recheck_shared_feedback.py")
        info["local_recovery_code_sha256"]={name:sha256(HERE/name) for name in names}
        for name in names:
            (self.output/name).write_bytes((HERE/name).read_bytes())
        return info


if __name__=="__main__":
    controller.RemoteQuality=RecoveredAreaEngine
    controller.REFERENCE_RECOVERY=recover_reference
    controller.VALID_SOURCE_BITS=(1,2,3)
    controller.clean_provenance=shared_repair
    controller.source_region=partial(source_region,allow_shared=True)
    controller.verify_labels=partial(verify_labels,allow_shared=True)
    controller.mesh_valid=mesh_valid_exact_contacts
    adaptive.mesh_valid=mesh_valid_exact_contacts
    controller.audit_candidate=adaptive.audit_adaptive
    controller.main()
