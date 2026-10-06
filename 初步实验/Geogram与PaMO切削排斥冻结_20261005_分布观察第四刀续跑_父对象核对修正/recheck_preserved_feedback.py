"""终态新固定几何反馈重新加载复审，沿用父链与几何协议并补充绑定验证。"""
import argparse
import json
from pathlib import Path
from functools import partial
import recheck_shared_feedback as shared
from run_constrained_batch import RemoteQuality
from preserved_saved_binding import collect_certificates,mesh_valid_saved_binding
from preserved_controller_source import replace_once


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args = parser.parse_args()
    report = json.loads((args.output/"01-反馈执行与独立审计.json").read_text(encoding="utf-8"))
    if report["status"] != "completed_with_recorded_failures":
        raise ValueError("运行中仅为快照，不能生成终态复审")
    certificates = collect_certificates(report)
    source = Path(shared.__file__).read_text(encoding="utf-8")
    old = "reference = trimesh.load(reference_path, process=True, validate=True) if reference_path.exists() else None"
    source = replace_once(source,old,"reference = load_bound_reference(reference_path, reference_row) if reference_path.exists() else None")
    source = "from preserved_saved_binding import load_bound_reference\n"+source
    snapshot = args.output/"recheck_preserved_saved_snapshot.py"
    snapshot.write_text(source,encoding="utf-8")
    namespace = dict(__name__="preserved_saved_recheck",__file__=str(snapshot))
    exec(compile(source,str(snapshot),"exec"),namespace)
    namespace["mesh_valid_exact_contacts"] = partial(mesh_valid_saved_binding,certificates=certificates)
    engine = RemoteQuality(args.output,args.port)
    try:
        # 原复审逐文件重加载、原点恢复、实际父摘要及累计参照协议保留。
        result = namespace["recheck"](args.prepared,args.output,engine)
        result["scope"] = "终态实际保存对象与精确证据绑定、真实父链、原固定顶点及双向几何探针；非连续距离和全域CCD证书"
        (args.output/"04-保存输出父链与几何复审.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        if result["passed"] != result["outputs"]:
            raise SystemExit(1)
    finally:
        engine.close()
