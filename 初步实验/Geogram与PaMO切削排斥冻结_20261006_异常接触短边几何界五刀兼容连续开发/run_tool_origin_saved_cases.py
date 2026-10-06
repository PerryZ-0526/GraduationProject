"""两张既有板体开发源的工具原点编码GPU验证，旧评价结果不改。"""

import argparse
import json
from pathlib import Path
import shutil

import trimesh

from audit_followup_candidate import sha256
from distribution_observation_engine import DistributionObservationEngine, audit_distribution_observation
from run_geometry_study import execute, save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--source-batch", type=Path, required=True)
    parser.add_argument("--reference-batch", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--build-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    previous = json.loads((args.source_batch / "01-统一配置完整父反馈记录.json").read_text("utf8"))
    manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
    references = json.loads((args.reference_batch / "01-独立累计参照绑定.json").read_text("utf8"))
    if previous["status"] != "completed_with_recorded_outcomes" or previous["protocol"]["stage1_SDF_offset_factor"] != .9:
        raise ValueError("必须绑定已终态原偏移板体开发对象")
    if previous["manifest_sha256"] != sha256(args.prepared / "01-完整范围冻结清单.json") or references["manifest_sha256"] != previous["manifest_sha256"]:
        raise ValueError("实际输入与独立参照绑定不同")
    route = next(r for r in manifest["routes"] if r["id"] == previous["selected_route"])
    args.output.mkdir(exist_ok=False)
    DistributionObservationEngine.prepared = args.prepared
    DistributionObservationEngine.side_validation = args.side_validation
    engine = DistributionObservationEngine(args.output, args.port)
    record = args.output / "01-工具原点两源GPU开发验证.json"
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，GPU预算两次，拒绝例与成功对照各一张",
              "文档概述": "两张实际源的孤立开发验证，不是新父反馈，不重写旧评价",
              "索引目录": ["environment", "rows"], "status": "running", "rows": [],
              "source_batch_sha256": sha256(args.source_batch / "01-统一配置完整父反馈记录.json"),
              "scope": "promoted_evaluation_failure_development_not_new_independent_evidence"}
    save(record, report)
    try:
        report["environment"] = engine.setup()
        build = json.loads(args.build_record.read_text("utf8"))
        extension = next(r for r in build["builds"] if r["variant"] == "sorted")
        if execute(engine.client, ["sha256sum", extension["extension"]])["stdout"].split()[0] != extension["extension_sha256"]:
            raise ValueError("排序扩展改变")
        for name, remote_name in [("run_constrained_worker.py", "original_run_constrained_worker.py"),
                                  ("sdf_bias_remesh.py", "sdf_bias_remesh.py"), ("tool_origin_encoding.py", "tool_origin_encoding.py")]:
            path = Path(__file__).with_name(name)
            engine.sftp.put(str(path), engine.remote + "/" + remote_name)
            if execute(engine.client, ["sha256sum", engine.remote + "/" + remote_name])["stdout"].split()[0] != sha256(path):
                raise ValueError("实际隔离模块摘要错误")
        for event in ("e1", "e0"):
            # 拒绝源优先，成功源作为编码是否破坏合法案例的对照；二者父对象都取旧实际记录。
            prior = next(r for r in previous["rows"] if r["event"] == event)
            inputs = args.source_batch / f"{route['id']}_{event}_candidate_input"
            source, labels = inputs / "clean_source.obj", inputs / "clean_labels.json"
            if event == "e0":
                if sha256(source) != prior["attempt"]["inputs_sha256"]["source.obj"] or sha256(labels) != prior["attempt"]["inputs_sha256"]["labels.json"]:
                    raise ValueError("成功对照源或标签与旧实际执行不同")
            else:
                # 拒绝例源没有旧GPU摘要，改为绑定已独立复制核对的v29实际对象。
                fixture = args.prepared.parent / "工具原点编码与内部再中心化负例_v29" / "01-工具原点与作者内部运算逐阶段诊断.json"
                frozen = json.loads(fixture.read_text("utf8"))
                for path, name in [(source, "偏移0.9_实际拒绝源.obj"), (labels, "偏移0.9_实际拒绝标签.json")]:
                    if sha256(path) != next(x["sha256"] for x in frozen["files"] if x["file"] == name):
                        raise ValueError("拒绝例与独立冻结实际源不同")
            info = next(t for t in route["prefix_tools"] if t["event_id"] == event)
            tool = args.prepared / "inputs" / info["mesh"]
            if sha256(tool) != info["sha256"]:
                raise ValueError("冻结工具摘要错误")
            origin = trimesh.load(tool, force="mesh", process=False).vertices.mean(axis=0).tolist()
            launcher = args.output / f"{event}_coordinate_launcher.py"
            launcher.write_text("\n".join([
                "import torch,hashlib,importlib.util,sys", "extension_path=" + repr(extension["extension"]),
                "assert hashlib.sha256(open(extension_path,'rb').read()).hexdigest()==" + repr(extension["extension_sha256"]),
                "spec=importlib.util.spec_from_file_location(" + repr(extension["module"]) + ",extension_path)",
                "extension=importlib.util.module_from_spec(spec)", "spec.loader.exec_module(extension)", "sys.modules['pamo._C']=extension",
                "from sdf_bias_remesh import install_bias", "install_bias(0.9)",
                "from tool_origin_encoding import install_tool_origin", "install_tool_origin(" + repr(origin) + ")",
                "from pamo_safe_project import Stage3Config", "import inspect",
                "assert hashlib.sha256(open(inspect.getfile(Stage3Config),'rb').read()).hexdigest()=='df1eb24db57394c32e31f6d67a58cd7ef6c25febc11aff39c5e9503ee82d6390'",
                "original=Stage3Config.__init__", "def larger(self,*args,**kwargs):", "    original(self,*args,**kwargs)",
                "    assert self.max_blocks==1<<25", "    self.max_blocks=1<<26", "Stage3Config.__init__=larger",
                "import original_run_constrained_worker as worker", "worker.main()"]), "utf8")
            engine.sftp.put(str(launcher), engine.remote + "/run_constrained_worker.py")
            if execute(engine.client, ["sha256sum", engine.remote + "/run_constrained_worker.py"])["stdout"].split()[0] != sha256(launcher):
                raise ValueError("实际坐标入口摘要错误")
            ref = args.output / f"{route['id']}_{event}_reference"
            shutil.copytree(args.reference_batch / ref.name, ref)
            reference_file = ref / "validated_reference.obj"
            if sha256(reference_file) != next(r["reference_sha256"] for r in references["rows"] if r["event"] == event):
                raise ValueError("复制后的独立累计参照摘要不同")
            destination = args.output / f"{route['id']}_{event}_candidate_boolean"
            row = {"event": event, "original_parent_sha256": prior["parent_sha256"],
                   "source_sha256": sha256(source), "labels_sha256": sha256(labels),
                   "actual_launcher_sha256": sha256(launcher), "origin_mm": origin, "status": "running"}
            report["rows"].append(row)
            save(record, report)
            result = engine.run(source, labels, tool, "boolean", destination)
            # 隔离编码及偏移适配都属于明确变体，不能继承原版方法标签。
            result.update(actual_gpu_method="isolated_tool_origin_FP64_before_FP32_full_PaMO_variant", stage1_SDF_offset_factor=.9)
            result = audit_distribution_observation(source, tool, labels, destination, result)
            row.update(status="completed", attempt=result)
            save(record, report)
            print(event, result["status"], flush=True)
        report.update(status="completed", finished_beijing=now(), GPU_budget=2,
                      summary={"cases": len(report["rows"]), "legal_saved": sum(r["attempt"]["status"] == "accepted_geometry_observation" for r in report["rows"])})
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
