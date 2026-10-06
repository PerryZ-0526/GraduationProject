"""原固定几何后端与条件性输入成对接入真实父反馈，全量保存对象门控。"""
import hashlib
import importlib.util
import json
from functools import partial
from pathlib import Path
import sys
from run_preserved_geometry_diagnostic import PreservedGeometryEngine
from run_constrained_batch import HERE,RemoteQuality
from run_geometry_study import execute,retrieve
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from preserved_controller_source import build_controller,build_reference,replace_once
from preserved_feedback_gate import check_preserved_mesh,audit_preserved_candidate
from locality_diagnostic import source_region,verify_labels

EXPECTED_CHECKER = "0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3"


class PreservedFeedbackEngine(PreservedGeometryEngine):
    def setup(self):
        info = super().setup()
        checker = execute(self.client,["sha256sum",CHECKER])["stdout"].split()[0]
        if checker != EXPECTED_CHECKER:
            raise ValueError("已通过六控制的精确检查器摘要改变")
        name = "preserved_geometry_precondition.py"
        self.sftp.put(str(HERE/name),self.remote+"/"+name)
        (self.output/name).write_bytes((HERE/name).read_bytes())
        worker = (self.output/"run_preserved_worker.py").read_text(encoding="utf-8")
        marker = "        before = mesh.vertices.copy()\n"
        guard = """        # 编码退化仅允许全部原固定几何顶点，包含自由点的面在GPU求解前拒绝。
        from preserved_geometry_precondition import require_fixed_degenerate_faces
        geometry_scale = 1.0 / np.ptp(source.vertices, axis=0).max()
        geometry_translation = -source.vertices.mean(axis=0)*geometry_scale
        details["fixed_geometry_arithmetic_precondition"] = require_fixed_degenerate_faces(
            mesh.vertices, mesh.faces, fixed, geometry_scale, geometry_translation)
"""
        worker = replace_once(worker,marker,guard+marker)
        target = self.output/"run_preserved_feedback_worker.py"
        target.write_text(worker,encoding="utf-8")
        self.sftp.put(str(target),self.remote+"/run_constrained_worker.py")
        for name in ("preserved_controller_source.py","preserved_feedback_gate.py","preserved_input_repair.py", "run_preserved_geometry_feedback.py"):
            (self.output/name).write_bytes((HERE/name).read_bytes())
        info.update(checker_sha256=checker,actual_feedback_worker_sha256=sha256(target),
            arithmetic_precondition_sha256=sha256(HERE/"preserved_geometry_precondition.py"),
            feedback_code_sha256={name:sha256(self.output/name) for name in ("preserved_controller_source.py","preserved_feedback_gate.py","preserved_input_repair.py","run_preserved_geometry_feedback.py")},
            scope="新固定几何真实父反馈，所有保存对象全量嵌入；候选仅一次局部加一次扩域，原版独立配对")
        return info

    def run(self,source,labels,tool,method,folder):
        actual = "planar_tangent_protected_preserved_geometry_areaguard_shared" if method == "boolean" else "expanded_tangent_protected_preserved_geometry_areaguard_shared" if method == "expanded" else method
        row = RemoteQuality.run(self,source,labels,tool,actual,folder)
        if method != "full":
            trace = self.remote+"/diff_trace.json"
            try:
                retrieve(self.client,self.sftp,trace,Path(folder)/"diff_trace.json")
                self.sftp.rename(trace,self.remote+"/"+Path(folder).name+"_diff_trace.json")
                calls = json.loads((Path(folder)/"diff_trace.json").read_text(encoding="utf-8"))["rows"]
                row["numerical_diagnostic"] = dict(diff_calls=len(calls),finite_energy_calls=sum(c["full_energy_finite"] for c in calls),
                    passed=bool(len(calls) == 50 and all(c["full_energy_finite"] and c["finite_positions"] and not c["nonfinite_free_vertices"] for c in calls)))
                row["diff_trace_sha256"] = sha256(Path(folder)/"diff_trace.json")
            except FileNotFoundError:
                row["numerical_diagnostic"] = dict(passed=row.get("projection") == "no_free_vertices_identity",trace_available=False)
        return row


def load_snapshot(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    # 独立保存新控制器源码；原状态机、原输入、旧分母和历史方法摘要保持原字节。
    identity = hashlib.sha256("\0".join(sys.argv[1:]).encode()).hexdigest()[:12]
    folder = HERE/"实验结果/固定几何控制器冻结副本"/identity
    folder.mkdir(parents=True,exist_ok=False)
    controller_path = folder/"preserved_controller.py"
    reference_path = folder/"preserved_reference.py"
    controller_path.write_text(build_controller((HERE/"run_constrained_feedback.py").read_text(encoding="utf-8")),encoding="utf-8")
    reference_path.write_text((HERE/"guarded_reference_recovery.py").read_text(encoding="utf-8"),encoding="utf-8")
    controller = load_snapshot("preserved_controller_"+identity,controller_path)
    reference = load_snapshot("preserved_reference_"+identity,reference_path)
    current = {}

    def factory(output,port):
        engine = PreservedFeedbackEngine(output,port)
        current["engine"] = engine
        (Path(output)/controller_path.name).write_bytes(controller_path.read_bytes())
        (Path(output)/reference_path.name).write_bytes(reference_path.read_bytes())
        return engine

    def recover(engine,prepared,route,event,initial_remote,output,reuse):
        mesh,record = reference.recover_reference(engine,prepared,route,event,initial_remote,output,reuse)
        if mesh is not None:
            valid,metrics = check_preserved_mesh(engine,Path(output)/"full_geometry_checks",mesh,"recovered_reference")
            record["validated_metrics"] = metrics
            record["accepted"] = valid
            if not valid:
                engine.independent_reference_cache.pop(route["id"],None)
                return None,record
        return mesh,record

    controller.RemoteQuality = factory
    controller.REFERENCE_RECOVERY = recover
    controller.VALID_SOURCE_BITS = (1,2,3)
    controller.source_region = partial(source_region,allow_shared=True)
    controller.verify_labels = partial(verify_labels,allow_shared=True)
    controller.audit_candidate = lambda *args: audit_preserved_candidate(current["engine"],*args)
    controller.main()


if __name__ == "__main__":
    main()
