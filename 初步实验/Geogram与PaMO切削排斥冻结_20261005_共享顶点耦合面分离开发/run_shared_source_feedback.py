"""保留共同来源位3，双表面核对后使用同来源共面切空间候选。"""
from functools import partial
from pathlib import Path
import run_constrained_feedback as controller
import run_adaptive_feedback as adaptive
from locality_cleanup import clean_provenance
from locality_diagnostic import source_region, verify_labels
from run_tangent_contact_feedback import ContactEngine
from run_constrained_batch import RemoteQuality, HERE
from audit_followup_candidate import sha256
from exact_alarm_contact import mesh_valid_exact_contacts


class SharedEngine(ContactEngine):
    def setup(self):
        info = super().setup()
        names = ("locality_masks.py", "planar_patch.py", "run_planar_worker.py")
        for name in names:
            self.sftp.put(str(HERE / name), self.remote + "/" + name)
            (self.output / name).write_bytes((HERE / name).read_bytes())
        info["shared_source_code_sha256"] = {name: sha256(HERE / name) for name in names}
        info["shared_source_policy"] = "保留位3，分别核对父及工具表面；共同来源区域独立重建"
        return info

    def run(self, source, labels, tool, method, folder):
        actual = "planar_tangent_shared" if method == "boolean" else "expanded_tangent_shared" if method == "expanded" else method
        return RemoteQuality.run(self, source, labels, tool, actual, folder)


def shared_cleanup(mesh, bits):
    """共同来源不进入仅支持单来源的碎片修复；仍需完整输入审计。"""
    if 3 not in bits:
        return adaptive.cleanup_and_repair(mesh, bits)
    clean, labels, details = clean_provenance(mesh, bits, allow_shared=True)
    details["shared_source_faces"] = int((labels == 3).sum())
    details["fragment_repair"] = {"triggered": False, "reason": "共同来源面不进行单来源碎片修复"}
    return clean, labels, details


if __name__ == "__main__":
    controller.RemoteQuality = SharedEngine
    controller.VALID_SOURCE_BITS = (1, 2, 3)
    controller.clean_provenance = shared_cleanup
    controller.source_region = partial(source_region, allow_shared=True)
    controller.verify_labels = partial(verify_labels, allow_shared=True)
    controller.mesh_valid = mesh_valid_exact_contacts
    adaptive.mesh_valid = mesh_valid_exact_contacts
    controller.audit_candidate = adaptive.audit_adaptive
    controller.main()
