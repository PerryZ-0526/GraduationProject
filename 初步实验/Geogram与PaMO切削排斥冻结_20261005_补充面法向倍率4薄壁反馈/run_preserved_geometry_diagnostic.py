"""原固定几何的完整碰撞投影隔离验证，保留正式输入退化拒绝。"""
from run_all_fixed_contact_diagnostic import AllContactEngine
from run_surface_band_source_diagnostic import main
from run_constrained_batch import HERE
from audit_followup_candidate import sha256


class PreservedGeometryEngine(AllContactEngine):
    def setup(self):
        info = super().setup()
        names = ("fixed_geometry_gpu.py", "preserved_collision_source.py", "preserved_collision_install.py", "preserved_geometry_system.py")
        for name in names:
            self.sftp.put(str(HERE/name), self.remote+"/"+name)
            (self.output/name).write_bytes((HERE/name).read_bytes())
        tangent = (HERE/"tangent_plane_gpu.py").read_text(encoding="utf-8")
        marker = "    system.set_constraints(fixed, normals)\n"
        if tangent.count(marker) != 1:
            raise ValueError("固定几何绑定位置不唯一")
        # 只在新隔离入口绑定投影前原坐标，末态再次验证所有固定点和失败标志。
        tangent = tangent.replace(marker, marker+"    system.bind_fixed_geometry(source, mesh)\n")
        end = "    torch.cuda.synchronize()\n"
        if tangent.count(end) != 1:
            raise ValueError("投影末态检查位置不唯一")
        tangent = tangent.replace(end, "    system.validate_fixed_geometry()\n"+end)
        target = self.output/"tangent_preserved_gpu.py"
        target.write_text(tangent, encoding="utf-8")
        self.sftp.put(str(target), self.remote+"/"+target.name)
        worker = (self.output/"run_surface_band_worker.py").read_text(encoding="utf-8")
        worker = worker.replace("from tangent_plane_gpu import project_on_planes", "from tangent_preserved_gpu import project_on_planes")
        worker = worker.replace("from precision_gradient_system import CollisionProtectedSystem", "from preserved_geometry_system import CollisionProtectedSystem")
        target = self.output/"run_preserved_worker.py"
        target.write_text(worker, encoding="utf-8")
        self.sftp.put(str(target), self.remote+"/run_constrained_worker.py")
        info["preserved_geometry_code_sha256"] = {name: sha256(self.output/name) for name in names}
        info["actual_preserved_worker_sha256"] = sha256(target)
        info["scope"] = "原固定接触常量能量与静态CCD；混合接触旧核体保留，隔离诊断不发布"
        return info


if __name__ == "__main__":
    main(PreservedGeometryEngine)
