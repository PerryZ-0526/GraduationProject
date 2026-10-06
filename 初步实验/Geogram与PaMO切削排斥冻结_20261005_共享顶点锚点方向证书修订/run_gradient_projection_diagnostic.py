"""新梯度的三个同源完整投影对照，单独冻结输出。"""
from run_precision_projection_diagnostic import PrecisionEngine, main
from run_constrained_batch import HERE
from audit_followup_candidate import sha256


class GradientEngine(PrecisionEngine):
    def setup(self):
        info = super().setup()
        names = ("robust_pt_gradient_gpu.py", "precision_gradient_install.py", "precision_gradient_system.py")
        for name in names:
            self.sftp.put(str(HERE / name), self.remote + "/" + name)
            (self.output / name).write_bytes((HERE / name).read_bytes())
        snapshot = self.output / "run_precision_worker.py"
        worker = snapshot.read_text(encoding="utf-8")
        marker = "from precision_collision_system import CollisionProtectedSystem"
        if worker.count(marker) != 1:
            raise ValueError("梯度投影要求唯一精度系统导入")
        snapshot.write_text(worker.replace(marker, "from precision_gradient_system import CollisionProtectedSystem"), encoding="utf-8")
        self.sftp.put(str(snapshot), self.remote + "/run_constrained_worker.py")
        info["gradient_code_sha256"] = {name: sha256(HERE / name) for name in names}
        info["actual_worker_sha256"] = sha256(snapshot)
        return info


if __name__ == "__main__":
    main(GradientEngine)
