from physical_feedback_gate import clean_for_backend as physical_clean_for_backend
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
    reference_path.write_text('"""独立参照逐步修复并绑定全量嵌入，避免将破损中间网格送入下一次布尔。"""\nimport numpy as np\nimport trimesh\nfrom audit_followup_candidate import sha256\nfrom locality_masks import save_obj_fp64\nfrom opposed_facet_cleanup import clean_cancel_opposed\nfrom physical_input_repair import repair_physical_input as repair_preserved_input\nfrom preserved_feedback_gate import check_preserved_mesh\nfrom recover_public_reference import prefix_tools_through\nfrom run_constrained_feedback import global_geometry\nfrom run_geometry_study import execute, retrieve, GEO\n\n\ndef recover_reference(engine, prepared, route, event, initial_remote, folder, reuse):\n    cache = getattr(engine, "guarded_reference_cache", {})\n    engine.guarded_reference_cache = cache\n    rid = route["id"]\n    folder.mkdir(parents=True, exist_ok=True)\n    destination = folder/"validated_reference.obj"\n    record = dict(accepted=False, route=rid, event=event, runs=[], steps=[],\n        independence="仅原初态与截至事件原工具；每步独立修复，不使用维护父网格",\n        continuous_geometry_certified=False)\n    if reuse and rid in cache:\n        path, digest, metrics = cache[rid]\n        if sha256(path) != digest:\n            raise ValueError("逐步参照缓存摘要变化")\n        destination.write_bytes(path.read_bytes())\n        record.update(accepted=True, kind="contained_reused_guarded_reference", output_sha256=digest,\n            validated_metrics=metrics)\n        return trimesh.load(destination, process=False), record\n    cache.pop(rid, None)\n    initial = prepared/"inputs"/route["initial_mesh"]\n    if sha256(initial) != route["initial_mesh_sha256"]:\n        raise ValueError("原初态摘要变化")\n    tools = prefix_tools_through(route, event)\n    record.update(initial_sha256=sha256(initial), tool_events=[t["event_id"] for t in tools],\n        tool_sha256=[t["sha256"] for t in tools])\n    parent = engine.remote+"/"+rid+"_"+event+"_guarded_initial.obj"\n    engine.sftp.put(str(initial), parent)\n    valid, metrics = check_preserved_mesh(engine, folder/"initial_checks",\n        trimesh.load(initial, process=False), "initial")\n    record["initial_metrics"] = metrics\n    if not valid:\n        record["status"] = "initial_rejected"\n        return None, record\n    for tool in tools:\n        source = prepared/"inputs"/tool["mesh"]\n        if sha256(source) != tool["sha256"]:\n            raise ValueError("原工具摘要变化")\n        step = folder/tool["event_id"]\n        step.mkdir(exist_ok=False)\n        remote_tool = parent+"_tool.obj"\n        output = parent+"_result.obj"\n        engine.sftp.put(str(source), remote_tool)\n        run = execute(engine.client, [GEO, parent, remote_tool, output], output+".log", timeout=120)\n        retrieve(engine.client, engine.sftp, output+".log", step/"geogram.log")\n        record["runs"].append(run)\n        if run["returncode"]:\n            record["status"] = "guarded_replay_boolean_failed"\n            return None, record\n        raw_path = step/"raw.obj"\n        retrieve(engine.client, engine.sftp, output, raw_path)\n        raw = trimesh.load(raw_path, process=False)\n        try:\n            clean, bits, cleanup = clean_cancel_opposed(raw, np.ones(len(raw.faces), int), allow_shared=True)\n            mesh, _, repair = repair_preserved_input(clean, bits)\n        except ValueError as error:\n            record.update(status="guarded_replay_cleanup_rejected", error=str(error))\n            return None, record\n        saved_path = step/"repaired.obj"\n        save_obj_fp64(mesh, saved_path)\n        saved = trimesh.load(saved_path, process=False)\n        geometry = global_geometry(saved, raw)\n        valid, metrics = check_preserved_mesh(engine, step/"checks", saved, "reference_step")\n        accepted = bool(repair["accepted_for_fixed_geometry_backend"] and valid and geometry["probe_max_mm"] <= 1e-7)\n        record["steps"].append(dict(event=tool["event_id"], raw_sha256=sha256(raw_path),\n            saved_sha256=sha256(saved_path), cleanup=cleanup, repair=repair,\n            raw_to_repaired_geometry=geometry, validated_metrics=metrics, accepted=accepted))\n        if not accepted:\n            record["status"] = "guarded_replay_intermediate_rejected"\n            return None, record\n        # 下一步只读取同一个已保存、全量核查并上传摘要匹配的中间对象。\n        parent = engine.remote+"/"+rid+"_"+event+"_guarded_after_"+tool["event_id"]+".obj"\n        engine.sftp.put(str(saved_path), parent)\n        if execute(engine.client, ["sha256sum", parent])["stdout"].split()[0] != sha256(saved_path):\n            raise ValueError("逐步参照上传摘要变化")\n    destination.write_bytes(saved_path.read_bytes())\n    record.update(accepted=True, status="guarded_replay_complete", kind="independent_guarded_replay",\n        output_sha256=sha256(destination), validated_metrics=metrics)\n    cache[rid] = (destination, record["output_sha256"], metrics)\n    return saved, record\n',encoding="utf-8")
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
    controller.clean_for_backend = physical_clean_for_backend
    controller.main()


if __name__ == "__main__":
    main()
