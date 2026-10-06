"""将碰撞导数数值保护接入共同来源与碎片修复的完整父反馈。"""
from functools import partial
from pathlib import Path
import run_constrained_feedback as controller
import run_adaptive_feedback as adaptive
from run_shared_repair_feedback import RepairEngine, shared_repair
from run_constrained_batch import RemoteQuality
from locality_diagnostic import source_region, verify_labels
from exact_alarm_contact import mesh_valid_exact_contacts
from audit_followup_candidate import sha256


class ProtectedEngine(RepairEngine):
    def setup(self):
        info=super().setup()
        path=Path(__file__).with_name("collision_protected_gpu.py")
        self.sftp.put(str(path),self.remote+"/"+path.name)
        (self.output/path.name).write_bytes(path.read_bytes())
        info["collision_protected_gpu_sha256"]=sha256(path)
        info["collision_policy"]="第一次求导，其他能量有限时增加固定新增点；完整碰撞和CCD不变"
        return info

    def run(self,source,labels,tool,method,folder):
        actual="planar_tangent_protected_shared" if method=="boolean" else "expanded_tangent_protected_shared" if method=="expanded" else method
        return RemoteQuality.run(self,source,labels,tool,actual,folder)


if __name__=="__main__":
    controller.RemoteQuality=ProtectedEngine
    controller.VALID_SOURCE_BITS=(1,2,3)
    controller.clean_provenance=shared_repair
    controller.source_region=partial(source_region,allow_shared=True)
    controller.verify_labels=partial(verify_labels,allow_shared=True)
    controller.mesh_valid=mesh_valid_exact_contacts
    adaptive.mesh_valid=mesh_valid_exact_contacts
    controller.audit_candidate=adaptive.audit_adaptive
    controller.main()
