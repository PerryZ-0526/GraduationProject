"""每个新点仅沿原共面区域的切空间优化，独立冻结连续验证。"""

import run_constrained_feedback as controller
from run_planar_feedback import PlanarEngine
from run_constrained_batch import RemoteQuality
from run_adaptive_feedback import cleanup_and_repair, audit_adaptive


class TangentEngine(PlanarEngine):
    def setup(self):
        info = super().setup()
        info["mechanism"] = "same_source_planar_regions_and_per_vertex_tangent_PAP_Pg_safe_projection"
        return info

    def run(self, source, labels, tool, method, folder):
        actual = "expanded_tangent" if method == "expanded" else "planar_tangent" if method == "boolean" else method
        return RemoteQuality.run(self, source, labels, tool, actual, folder)


def main():
    controller.RemoteQuality = TangentEngine
    controller.clean_provenance = cleanup_and_repair
    controller.audit_candidate = audit_adaptive
    controller.main()


if __name__ == "__main__":
    main()
