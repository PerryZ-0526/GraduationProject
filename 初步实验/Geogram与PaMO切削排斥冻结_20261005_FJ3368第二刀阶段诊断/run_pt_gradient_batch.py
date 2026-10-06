"""同一冻结100查询的GPU距离梯度与独立权重参照比较。"""
import argparse
import json
from pathlib import Path
import numpy as np
from run_constrained_batch import HERE,RemoteQuality
from run_geometry_study import execute,retrieve,save,now,PYTHON
from audit_followup_candidate import sha256
from pt_gradient_reference import point_triangle_gradient


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    engine=RemoteQuality(args.output,args.port)
    try:
        if execute(engine.client,["mkdir",engine.remote])["returncode"]:
            raise RuntimeError("远端梯度诊断目录不可创建")
        names=("robust_pt_gpu.py","robust_pt_gradient_gpu.py","run_pt_gradient_worker.py")
        for name in names:
            engine.sftp.put(str(HERE/name),engine.remote+"/"+name)
            (args.output/name).write_bytes((HERE/name).read_bytes())
        engine.sftp.put(str(args.inputs),engine.remote+"/inputs.json")
        (args.output/"inputs.json").write_bytes(args.inputs.read_bytes())
        run=execute(engine.client,["env","LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6","PYTHONPATH="+engine.remote,
            PYTHON,engine.remote+"/run_pt_gradient_worker.py","--inputs",engine.remote+"/inputs.json","--output",engine.remote+"/result.json"],engine.remote+"/worker.log",timeout=300)
        retrieve(engine.client,engine.sftp,engine.remote+"/worker.log",args.output/"worker.log")
        save(args.output/"01-梯度GPU执行记录.json",{"time_beijing":now(),"run":run,
            "source_sha256":{name:sha256(HERE/name) for name in [*names,"pt_gradient_reference.py"]},"inputs_sha256":sha256(args.inputs)})
        if run["returncode"]:
            raise RuntimeError("梯度诊断执行失败")
        retrieve(engine.client,engine.sftp,engine.remote+"/result.json",args.output/"result.json")
        result=json.loads((args.output/"result.json").read_text(encoding="utf-8"))
        gradients=result["gradients"]
        rows=[]
        for case,observed in zip(json.loads(args.inputs.read_text(encoding="utf-8"))["cases"],gradients,strict=True):
            try:
                expected=point_triangle_gradient(np.array(case["positions_normalized"],np.float32))
            except ValueError as error:
                rows.append({"id":case["id"],"status":"outside_smooth_derivative_protocol","reason":str(error)})
                continue
            values=np.array(observed)
            finite=bool(np.isfinite(values).all())
            difference=float(np.max(np.abs(values-expected))) if finite else None
            improved=np.array(result["improved_gradients"][len(rows)])
            improved_finite=bool(np.isfinite(improved).all())
            improved_error=float(np.max(np.abs(improved-expected))) if improved_finite else None
            rows.append({"id":case["id"],"status":"audited","finite":finite,"max_absolute_error":difference,
                "passed":bool(finite and difference<=1e-3),"expected":expected.tolist(),"observed":observed,
                "improved_finite":improved_finite,"improved_error":improved_error,
                "improved_passed":bool(improved_finite and improved_error<=1e-3)})
        selected=[row for row in rows if row["status"]=="audited"]
        report={"time_beijing":now(),"rows":rows,"passed":sum(row["passed"] for row in selected),"audited":len(selected),
            "improved_passed":sum(row["improved_passed"] for row in selected),
            "scope":"距离梯度数值对拍，绝对容差1e-3；不是完整碰撞Hessian或连续输出证书"}
        save(args.output/"02-距离梯度独立参照审计.json",report)
        print(report["passed"],report["improved_passed"],report["audited"],flush=True)
    finally:
        engine.close()
