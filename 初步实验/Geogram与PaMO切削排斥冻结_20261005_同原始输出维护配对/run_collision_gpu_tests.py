"""在已准备的隔离环境运行数值策略CUDA测试，保留每次日志。"""
import argparse
from pathlib import Path
from run_constrained_batch import RemoteQuality,HERE
from run_geometry_study import execute,retrieve,PYTHON,now,save
from audit_followup_candidate import sha256


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,required=True)
    args=parser.parse_args()
    output=HERE/"实验结果/20261004_碰撞导数保护五输入GPU对照"
    engine=RemoteQuality(output,args.port)
    try:
        path=HERE/"test_collision_protected_gpu.py"
        engine.sftp.put(str(path),engine.remote+"/"+path.name)
        (output/path.name).write_bytes(path.read_bytes())
        run=execute(engine.client,["env","LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6","PYTHONPATH="+engine.remote,
            PYTHON,engine.remote+"/"+path.name],engine.remote+"/policy_tests_v2.log",timeout=120)
        retrieve(engine.client,engine.sftp,engine.remote+"/policy_tests_v2.log",output/"04-CUDA策略显式初始化测试日志.txt")
        save(output/"05-CUDA策略显式初始化执行记录.json",dict(time_beijing=now(),run=run,source_sha256=sha256(path)))
        print(run["returncode"])
        print((output/"04-CUDA策略显式初始化测试日志.txt").read_text(encoding="utf-8")[-1200:])
    finally:
        engine.close()
