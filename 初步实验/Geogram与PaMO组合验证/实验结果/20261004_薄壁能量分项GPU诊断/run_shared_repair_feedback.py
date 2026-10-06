"""共同来源保持、精确接触复核和碎片修复组成新的连续开发方法。"""
from pathlib import Path
import run_constrained_feedback as controller
import run_adaptive_feedback as adaptive
from functools import partial
from run_shared_source_feedback import SharedEngine
from locality_cleanup import clean_provenance
from locality_diagnostic import source_region, verify_labels
from locality_retriangulate import invalid_faces
from fragment_pipeline import repair_input
from exact_alarm_contact import mesh_valid_exact_contacts
from audit_followup_candidate import sha256


class RepairEngine(SharedEngine):
    def setup(self):
        info = super().setup()
        names = ("run_shared_repair_feedback.py", "fragment_pipeline.py", "locality_retriangulate.py",
                 "locality_sliver_collapse.py", "locality_cleanup.py", "locality_diagnostic.py")
        for name in names:
            path = Path(__file__).with_name(name)
            (self.output / name).write_bytes(path.read_bytes())
        info["shared_repair_sha256"] = {name: sha256(Path(__file__).with_name(name)) for name in names}
        info["repair_policy"] = "同来源碎片翻边折叠与整体回滚，保留位3；原面积及几何门槛不变"
        return info


def shared_repair(mesh, bits):
    """每帧同样处理，失败回滚原清理输入并保留原门控拒绝。"""
    clean, labels, details = clean_provenance(mesh, bits, allow_shared=True)
    if invalid_faces(clean.vertices, clean.faces).any():
        clean, labels, repair = repair_input(clean, labels, audit=mesh_valid_exact_contacts, allow_shared=True)
        details["fragment_repair"] = repair
    else:
        details["fragment_repair"] = {"triggered": False, "reason": "无面积门槛内面"}
    return clean, labels, details


if __name__ == "__main__":
    controller.RemoteQuality = RepairEngine
    controller.VALID_SOURCE_BITS = (1, 2, 3)
    controller.clean_provenance = shared_repair
    controller.source_region = partial(source_region, allow_shared=True)
    controller.verify_labels = partial(verify_labels, allow_shared=True)
    controller.mesh_valid = mesh_valid_exact_contacts
    adaptive.mesh_valid = mesh_valid_exact_contacts
    controller.audit_candidate = adaptive.audit_adaptive
    controller.main()
