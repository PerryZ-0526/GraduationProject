"""复用完整父反馈控制，接入碎片修复与新接缝机制，保留原版配对分支。"""

import json
from pathlib import Path
from time import perf_counter
import trimesh

import run_constrained_feedback as controller
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import now
from audit_followup_candidate import sha256, quality_distribution
from geometry_preservation_audit import mesh_valid
from fragment_pipeline import repair_input
from locality_retriangulate import invalid_faces
from locality_cleanup import clean_provenance


class AdaptiveEngine(RemoteQuality):
    """只替换本次隔离工作目录入口，作者CUDA扩展和旧冻结方法保持原样。"""
    def setup(self):
        info = super().setup()
        files = ("adaptive_seam.py", "run_adaptive_worker.py", "planar_quality.py", "locality_retriangulate.py")
        for name in files:
            self.sftp.put(str(HERE / name), self.remote + "/" + name)
            (self.output / name).write_bytes((HERE / name).read_bytes())
        self.sftp.put(str(HERE / "run_adaptive_worker.py"), self.remote + "/run_constrained_worker.py")
        info["adaptive_code_sha256"] = {name: sha256(HERE / name) for name in files}
        info["controller_code_sha256"] = {name: sha256(HERE / name) for name in (
            "run_adaptive_feedback.py", "run_constrained_feedback.py", "fragment_pipeline.py",
            "locality_cleanup.py", "locality_sliver_collapse.py", "geometry_preservation_audit.py")}
        info["mechanism"] = "long_constraint_subdivision_then_planar_quality_then_local_CGAL_and_full_GPU_projection"
        return info

    def run(self, source, labels, tool, method, folder):
        actual = "adaptive_planar" if method == "boolean" else method
        return super().run(source, labels, tool, actual, folder)


def cleanup_and_repair(mesh, bits):
    """两条分支使用相同碎片处理，原始CSG文件保留；后续继续核对父面来源。"""
    clean, labels, details = clean_provenance(mesh, bits)
    if invalid_faces(clean.vertices, clean.faces).any():
        repaired, labels, repair = repair_input(clean, labels)
        details["fragment_repair"] = repair
        clean = repaired
    else:
        details["fragment_repair"] = {"triggered": False, "reason": "无FP64或FP32退化面"}
    return clean, labels, details


def audit_adaptive(source_path, tool_path, labels_path, folder, row):
    """完整输出独立审计；共面改三角化后的外部保持由固定候选契约核对。"""
    if row["execution"]["returncode"]:
        return row
    started = perf_counter()
    source = trimesh.load(source_path, force="mesh", process=False)
    candidate = trimesh.load(Path(folder) / "candidate.obj", force="mesh", process=False)
    valid, metrics = mesh_valid(candidate)
    geometry = controller.global_geometry(candidate, source)
    log = (Path(folder) / "worker.log").read_text(encoding="utf-8")
    capacity = "exceeds max_blocks" in log or "Number of contacts" in log
    same_topology = candidate.euler_number == source.euler_number and len(candidate.split(only_watertight=False)) == len(source.split(only_watertight=False))
    contract = row.get("fixed_contract")
    passed = valid and same_topology and geometry["probe_max_mm"] <= .1 and not capacity
    if row["method"] != "full":
        passed = passed and contract is not None and contract["passed"]
    row.update(output_metrics=metrics, geometry_to_maintenance_source=geometry, quality=quality_distribution(candidate),
               source_quality=quality_distribution(source), capacity_changed=capacity, continuous_geometry_certified=False,
               audited_source_sha256=sha256(source_path), independent_audit_ms=(perf_counter() - started) * 1000,
               status="accepted_sampled" if passed else "audit_rejected", audit_time_beijing=now())
    return row


def main():
    # 复用已审计的物理前缀、父链、拒绝保留与版本控制，不复制整套状态机。
    controller.RemoteQuality = AdaptiveEngine
    controller.clean_provenance = cleanup_and_repair
    controller.audit_candidate = audit_adaptive
    controller.main()


if __name__ == "__main__":
    main()
