"""冻结并运行原固定接触能量、CCD及混合运动CUDA控制。"""
import argparse
import getpass
import os
from pathlib import Path
import paramiko
from audit_followup_candidate import sha256
from run_geometry_study import execute,retrieve,save,now,PYTHON,REMOTE_BASE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    here = Path(__file__).parent
    assets = here.parent/"可复用磨削测试集/全部固定接触原几何CUDA回归_v1/inputs"
    paths = [here/name for name in ("preserved_collision_controls_gpu.py","precision_gradient_install.py",
        "precision_collision_install.py","robust_pt_gpu.py","robust_pt_gradient_gpu.py","fixed_geometry_gpu.py",
        "preserved_collision_source.py","preserved_collision_install.py")]+[assets/"queries.npz",assets/"contact_audit.json"]
    for path in paths:
        (args.output/path.name).write_bytes(path.read_bytes())
    save(args.output/"01-原固定接触CUDA控制冻结.json",dict(time_beijing=now(),published=False,
        files={path.name:sha256(path) for path in paths},scope="完整碰撞核的静态与混合运动控制，不发布"))
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.connect(os.environ.get("GPU_SSH_HOST","connect.westb.seetacloud.com"),port=args.port,username="root",
        password=getpass.getpass("GPU SSH password: "),look_for_keys=False,allow_agent=False,timeout=30)
    sftp = client.open_sftp()
    remote = REMOTE_BASE+"/preserved_controls_"+args.output.name
    try:
        if execute(client,["mkdir",remote])["returncode"]:
            raise RuntimeError("隔离目录已存在")
        for path in paths:
            sftp.put(str(path),remote+"/"+path.name)
        result = execute(client,["env","LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6","PYTHONPATH="+remote,PYTHON,
            remote+"/preserved_collision_controls_gpu.py","--queries",remote+"/queries.npz","--binding",remote+"/contact_audit.json",
            "--output",remote+"/result.json"],remote+"/worker.log",timeout=180)
        retrieve(client,sftp,remote+"/worker.log",args.output/"worker.log")
        # 无结果时保留真实编译或执行失败，不以取回异常掩盖远端日志。
        try:
            retrieve(client,sftp,remote+"/result.json",args.output/"02-CUDA控制结果.json")
        except FileNotFoundError:
            pass
        save(args.output/"03-实际执行记录.json",dict(time_beijing=now(),execution=result,published=False))
        print(result["returncode"])
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
