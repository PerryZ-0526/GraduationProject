"""把全部已归因固定接触和解析控制交给新实例CUDA核进行独立验证。"""
import argparse
import getpass
import os
from pathlib import Path
import json
import numpy as np
import paramiko
from run_geometry_study import execute, retrieve, save, now, PYTHON, REMOTE_BASE
from audit_followup_candidate import sha256
from pt_exact_reference import point_triangle_reference
from ee_exact_reference import edge_edge_reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    rows = [dict(method=method["method"], **row) for method in json.loads(args.record.read_text(encoding="utf-8"))["methods"] for row in method["rows"]]
    if any(row["status"] != "quantization_lost_positive_separation" for row in rows):
        raise ValueError("当前查询清单含未归因接触，不能混为量化修复验证")
    queries = [(row["points_fp64_mm"], row["type"]) for row in rows]
    # 真零距离、退化和偏斜控制一并冻结，不能通过返回正数掩盖真实相交。
    controls = [([[0,0,0],[1,0,0],[0,1,0],[.2,.2,1]],3),
                ([[.2,.2,0],[0,0,0],[1,0,0],[0,1,0]],3),
                ([[0,0,0],[1,0,0],[0,0,0],[0,0,0]],3),
                ([[0,0,0],[1,0,0],[.5,-1,0],[.5,1,0]],4),
                ([[0,0,0],[1,0,0],[0,1,1],[1,1,1]],4),
                ([[0,0,0],[1,0,0],[.2,0,0],[.8,0,0]],4)]
    queries += controls
    references = [(point_triangle_reference if kind == 3 else edge_edge_reference)(points)[1] for points, kind in queries]
    np.savez(args.output / "queries.npz", points=np.array([p for p,k in queries]),
             types=np.array([k for p,k in queries],dtype=np.int32), reference=np.array(references))
    save(args.output / "01-固定原几何CUDA查询冻结.json", dict(time_beijing=now(), input_record_sha256=sha256(args.record),
        contact_observations=len(rows), analytic_controls=len(controls), rows=rows, controls=controls,
        queries_sha256=sha256(args.output / "queries.npz"), published=False))
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.connect(os.environ.get("GPU_SSH_HOST", "connect.westb.seetacloud.com"), port=args.port,
                   username="root", password=getpass.getpass("GPU SSH password: "), look_for_keys=False, allow_agent=False, timeout=30)
    sftp = client.open_sftp()
    remote = REMOTE_BASE + "/fixed_geometry_" + args.output.name
    try:
        if execute(client,["mkdir",remote])["returncode"]:
            raise RuntimeError("隔离目录已存在")
        for path in (Path(__file__), Path(__file__).with_name("fixed_geometry_gpu.py"),
                     Path(__file__).with_name("robust_pt_gpu.py"), args.output / "queries.npz"):
            sftp.put(str(path),remote+"/"+path.name)
            if path.suffix == ".py":
                (args.output/path.name).write_bytes(path.read_bytes())
        result = execute(client,["env","LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6","PYTHONPATH="+remote,
            PYTHON,remote+"/fixed_geometry_gpu.py","--queries",remote+"/queries.npz","--output",remote+"/result.json"],
            remote+"/worker.log",timeout=120)
        retrieve(client,sftp,remote+"/worker.log",args.output/"worker.log")
        retrieve(client,sftp,remote+"/result.json",args.output/"02-CUDA距离对拍.json")
        save(args.output/"03-实际执行记录.json",dict(time_beijing=now(),execution=result,
            code_sha256={name:sha256(args.output/name) for name in ("fixed_geometry_gpu.py","robust_pt_gpu.py")},published=False))
        print(result["returncode"])
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
