"""闭合非凸工具的表面邻域版本，独立冻结并保留旧凸域负结果。"""
from run_gradient_pair_feedback import GradientPairEngine, main
from run_constrained_batch import HERE
from audit_followup_candidate import sha256


class SurfaceBandEngine(GradientPairEngine):
    def setup(self):
        info = super().setup()
        name = "tool_surface_band.py"
        self.sftp.put(str(HERE/name), self.remote+"/"+name)
        (self.output/name).write_bytes((HERE/name).read_bytes())
        worker = (self.output/"run_gradient_worker.py").read_text(encoding="utf-8")
        start = worker.index("        # 使用凸工具面平面各外移0.1毫米的交集作为求解域")
        end = worker.index("        outside_faces =", start)
        # 凸工具逐行保留原数学规则，只对原本拒绝的非凸工具增加独立分支。
        convex_start = worker.index("        normals = tool.face_normals", start)
        convex_body = worker[convex_start:end]
        replacement = "        # 凸工具沿用原面平面余量；非凸工具使用实际表面距离带。\n        if tool.is_convex:\n" + "\n".join("    "+line for line in convex_body.rstrip().split("\n")) + "\n        else:\n            from tool_surface_band import surface_band\n            near = surface_band(mesh.vertices, tool, .1)\n"
        worker = worker[:start]+replacement+worker[end:]
        worker = worker.replace('"convex_polyhedral_face_plane_margin_0_1_mm"', '"convex_polyhedral_face_plane_margin_0_1_mm" if tool.is_convex else "closed_tool_surface_distance_band_0_1_mm"')
        snapshot = self.output/"run_surface_band_worker.py"
        snapshot.write_text(worker, encoding="utf-8")
        self.sftp.put(str(snapshot), self.remote+"/run_constrained_worker.py")
        info["surface_band_code_sha256"] = sha256(HERE/name)
        info["actual_surface_band_worker_sha256"] = sha256(snapshot)
        info["free_domain"] = "convex_original_plane_margin_or_nonconvex_closed_surface_band_0_1_mm"
        return info


if __name__ == "__main__":
    main(SurfaceBandEngine)
