"""共面区域重建接入同一连续状态机，依赖安装限于本批隔离目录。"""

import json
import run_constrained_feedback as controller
from run_constrained_batch import RemoteQuality, HERE
from run_adaptive_feedback import cleanup_and_repair, audit_adaptive
from run_geometry_study import execute, retrieve, PYTHON
from audit_followup_candidate import sha256


class PlanarEngine(RemoteQuality):
    """继承输入摘要和独立进程协议，额外安装固定Triangle版本。"""
    def setup(self):
        info = super().setup()
        names = ("planar_patch.py", "run_planar_worker.py", "tangent_plane_gpu.py")
        for name in names:
            self.sftp.put(str(HERE / name), self.remote + "/" + name)
            (self.output / name).write_bytes((HERE / name).read_bytes())
        self.sftp.put(str(HERE / "run_planar_worker.py"), self.remote + "/run_constrained_worker.py")
        installed = execute(self.client, [PYTHON, "-m", "pip", "install", "--target", self.remote,
                                         "--no-deps", "triangle==20250106"], self.remote + "/triangle_install.log", timeout=180)
        retrieve(self.client, self.sftp, self.remote + "/triangle_install.log", self.output / "triangle_install.log")
        if installed["returncode"]:
            raise RuntimeError("隔离Triangle依赖安装失败")
        actual = execute(self.client, ["env", "PYTHONPATH=" + self.remote, PYTHON, "-c",
            "import triangle,triangle.core,hashlib,json;print(json.dumps({'version':triangle.__version__,'binary_sha256':hashlib.sha256(open(triangle.core.__file__,'rb').read()).hexdigest()}))"])
        if actual["returncode"]:
            raise RuntimeError("Triangle实际依赖读取失败")
        info.update(planar_code_sha256={name: sha256(HERE / name) for name in names},
                    triangle=json.loads(actual["stdout"].strip().splitlines()[-1]),
                    mechanism="same_source_planar_regions_with_holes_then_PaMO_safe_projection",
                    geometry_generation="CPU_Triangle", projection="GPU_if_free_vertices_else_identity")
        return info

    def run(self, source, labels, tool, method, folder):
        return super().run(source, labels, tool, "planar" if method == "boolean" else method, folder)


def main():
    controller.RemoteQuality = PlanarEngine
    controller.clean_provenance = cleanup_and_repair
    controller.audit_candidate = audit_adaptive
    controller.main()


if __name__ == "__main__":
    main()
