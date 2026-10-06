"""切空间候选配合精确共享接触复核，另开开发父链，保留全部旧协议结果。"""
from pathlib import Path
import run_adaptive_feedback as adaptive
import run_constrained_feedback as controller
from run_tangent_feedback import TangentEngine
from exact_alarm_contact import mesh_valid_exact_contacts
from audit_followup_candidate import sha256


class ContactEngine(TangentEngine):
    def setup(self):
        info = super().setup()
        path = Path(__file__).with_name("exact_alarm_contact.py")
        (self.output / path.name).write_bytes(path.read_bytes())
        info["exact_contact_audit_sha256"] = sha256(path)
        info["contact_scope"] = "仅原报警集合，精确证明共享单纯形接触；不认证完整无自交"
        return info


if __name__ == "__main__":
    # 输入和输出使用同一补强复核；面积、几何、容量及父状态检查不变。
    controller.RemoteQuality = ContactEngine
    controller.clean_provenance = adaptive.cleanup_and_repair
    adaptive.mesh_valid = mesh_valid_exact_contacts
    controller.mesh_valid = mesh_valid_exact_contacts
    controller.audit_candidate = adaptive.audit_adaptive
    controller.main()
