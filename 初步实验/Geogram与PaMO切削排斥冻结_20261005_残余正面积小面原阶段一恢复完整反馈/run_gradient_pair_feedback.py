"""新梯度单独版本的完整连续反馈，不用于旧精度批次续跑。"""
from functools import partial
import argparse
from pathlib import Path
import sys
import run_constrained_feedback as controller
import run_adaptive_feedback as adaptive
from run_precision_pair_feedback import PrecisionPairEngine
from run_opposed_pair_feedback import pair_repair
from run_constrained_batch import HERE, RemoteQuality
from independent_reference_recovery import recover_reference
from locality_diagnostic import source_region, verify_labels
from exact_alarm_contact import mesh_valid_exact_contacts
from audit_followup_candidate import sha256


class GradientPairEngine(PrecisionPairEngine):
    def setup(self):
        info = super().setup()
        names = ("robust_pt_gradient_gpu.py", "precision_gradient_install.py", "precision_gradient_system.py")
        for name in names:
            self.sftp.put(str(HERE / name), self.remote + "/" + name)
            (self.output / name).write_bytes((HERE / name).read_bytes())
        snapshot = self.output / "run_gradient_worker.py"
        template = (self.output / "run_precision_worker.py").read_text(encoding="utf-8")
        marker = "from precision_collision_system import CollisionProtectedSystem"
        if template.count(marker) != 1:
            raise ValueError("连续梯度工作进程导入不唯一")
        snapshot.write_text(template.replace(marker, "from precision_gradient_system import CollisionProtectedSystem"), encoding="utf-8")
        self.sftp.put(str(snapshot), self.remote + "/run_constrained_worker.py")
        info["gradient_code_sha256"] = {name: sha256(HERE / name) for name in names}
        info["actual_gradient_worker_sha256"] = sha256(snapshot)
        return info

    def run(self, source, labels, tool, method, folder):
        actual = "planar_tangent_protected_gradient_areaguard_shared" if method == "boolean" else "expanded_tangent_protected_gradient_areaguard_shared" if method == "expanded" else method
        return RemoteQuality.run(self, source, labels, tool, actual, folder)


def main(engine_type=GradientPairEngine):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--prepared", type=Path)
    args, _ = parser.parse_known_args(sys.argv[1:])
    # 新梯度必须另建版本，不能把结果写入旧版本断连续跑分母。
    if args.prepared and (args.prepared / "02-断连续跑协议.json").exists():
        raise ValueError("新梯度不能用于旧精度续跑输入")
    controller.RemoteQuality = engine_type
    controller.REFERENCE_RECOVERY = recover_reference
    controller.VALID_SOURCE_BITS = (1, 2, 3)
    controller.clean_provenance = pair_repair
    controller.source_region = partial(source_region, allow_shared=True)
    controller.verify_labels = partial(verify_labels, allow_shared=True)
    controller.mesh_valid = mesh_valid_exact_contacts
    adaptive.mesh_valid = mesh_valid_exact_contacts
    controller.audit_candidate = adaptive.audit_adaptive
    controller.main()


if __name__ == "__main__":
    main()
