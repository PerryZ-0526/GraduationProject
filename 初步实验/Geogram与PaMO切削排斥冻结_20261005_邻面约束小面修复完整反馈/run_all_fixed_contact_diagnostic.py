"""全部异常接触的隔离GPU诊断，不修改正式反馈门控或既有诊断副本。"""
from run_surface_band_feedback import SurfaceBandEngine
from run_surface_band_source_diagnostic import main
from run_constrained_batch import HERE
from audit_followup_candidate import sha256


class AllContactEngine(SurfaceBandEngine):
    def setup(self):
        info = super().setup()
        source = (HERE / "collision_diff_diagnostic.py").read_text(encoding="utf-8")
        marker = "for index in bad_contacts[:20]:"
        if source.count(marker) != 1:
            raise ValueError("异常接触采样入口不唯一")
        # 只在新隔离副本解除JSON样本截断，保留完整求导与原拒绝流程。
        source = source.replace(marker, "for index in bad_contacts:")
        source = source.replace("# 限制JSON例数，同时保存总数；记录每个零距离接触是否仍含自由点。",
                                "# 保存全部异常接触，逐项绑定原固定几何，不截断样本。")
        target = self.output / "all_contact_diff_diagnostic.py"
        target.write_text(source, encoding="utf-8")
        self.sftp.put(str(target), self.remote + "/" + target.name)
        system = (HERE / "precision_gradient_system.py").read_text(encoding="utf-8")
        system = system.replace("from collision_diff_diagnostic import", "from all_contact_diff_diagnostic import")
        snapshot = self.output / "precision_gradient_system.py"
        snapshot.write_text(system, encoding="utf-8")
        self.sftp.put(str(snapshot), self.remote + "/" + snapshot.name)
        info["all_contact_diagnostic_sha256"] = sha256(target)
        info["actual_diagnostic_system_sha256"] = sha256(snapshot)
        return info


if __name__ == "__main__":
    main(AllContactEngine)
