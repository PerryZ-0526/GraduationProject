"""反向面清理和碰撞分类精度修复接入完整反馈，输出门槛保持原样。"""
from functools import partial
import json
import sys
from verify_precision_resume import preflight
import run_constrained_feedback as controller
import run_adaptive_feedback as adaptive
from run_opposed_pair_feedback import PairEngine,pair_repair
from run_constrained_batch import HERE,RemoteQuality
from independent_reference_recovery import recover_reference
from locality_diagnostic import source_region,verify_labels
from exact_alarm_contact import mesh_valid_exact_contacts
from audit_followup_candidate import sha256


class PrecisionPairEngine(PairEngine):
    def setup(self):
        info=super().setup()
        names=("robust_pt_gpu.py","precision_collision_install.py","precision_collision_system.py","collision_diff_diagnostic.py")
        for name in names:
            self.sftp.put(str(HERE/name),self.remote+"/"+name)
            (self.output/name).write_bytes((HERE/name).read_bytes())
        worker=(HERE/"run_planar_worker.py").read_text(encoding="utf-8")
        marker="from collision_protected_gpu import CollisionProtectedSystem"
        if worker.count(marker)!=1:
            raise ValueError("精度反馈要求唯一碰撞系统导入")
        snapshot=self.output/"run_precision_worker.py"
        snapshot.write_text(worker.replace(marker,"from precision_collision_system import CollisionProtectedSystem"),encoding="utf-8")
        self.sftp.put(str(snapshot),self.remote+"/run_constrained_worker.py")
        info["precision_code_sha256"]={name:sha256(HERE/name) for name in names}
        info["actual_precision_worker_sha256"]=sha256(snapshot)
        return info

    def run(self,source,labels,tool,method,folder):
        actual="planar_tangent_protected_precision_areaguard_shared" if method=="boolean" else "expanded_tangent_protected_precision_areaguard_shared" if method=="expanded" else method
        return RemoteQuality.run(self,source,labels,tool,actual,folder)


if __name__=="__main__":
    # 续跑在连接远端之前核对旧记录、完整分母和实际方法摘要。
    continuation = preflight(sys.argv[1:], HERE)
    if continuation is not None:
        print(json.dumps(continuation, ensure_ascii=False, indent=2))
    controller.RemoteQuality=PrecisionPairEngine
    controller.REFERENCE_RECOVERY=recover_reference
    controller.VALID_SOURCE_BITS=(1,2,3)
    controller.clean_provenance=pair_repair
    controller.source_region=partial(source_region,allow_shared=True)
    controller.verify_labels=partial(verify_labels,allow_shared=True)
    controller.mesh_valid=mesh_valid_exact_contacts
    adaptive.mesh_valid=mesh_valid_exact_contacts
    controller.audit_candidate=adaptive.audit_adaptive
    controller.main()
