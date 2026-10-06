"""使用隔离精度CCD核执行解析运动控制，保留原slackness和迭代逻辑。"""
import argparse
import json
from pathlib import Path
import numpy as np
import warp as wp
import pamo_safe_project.energy as energy
from precision_collision_install import install_precision_collision


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    wp.init()
    original=energy.accd_kernel
    install=install_precision_collision()
    rows=[]
    for case in json.loads(args.inputs.read_text(encoding="utf-8"))["cases"]:
        points=wp.array(np.array(case["points"],np.float32),dtype=wp.vec3,device="cuda:0")
        velocity=wp.array(np.array(case["velocities"],np.float32),dtype=wp.vec3,device="cuda:0")
        counter=wp.array([1],dtype=int,device="cuda:0")
        types=wp.array([[3,0]],dtype=int,device="cuda:0")
        indices=wp.array([[0,1,2,3]],dtype=int,device="cuda:0")
        results=[]
        for kernel in [original,energy.accd_kernel]:
            step=wp.array([1.0],dtype=float,device="cuda:0")
            wp.launch(kernel,dim=1,inputs=[counter,points,velocity,types,indices,.9,0.0,100,.001],outputs=[step],device="cuda:0")
            wp.synchronize_device("cuda:0")
            results.append(float(step.numpy()[0]))
        improved=results[1]
        passed=bool(np.isfinite(improved) and 0<=improved<=case["maximum_safe_step"]+1e-6)
        if case["expect_full_step"]:
            passed=passed and abs(improved-1)<1e-6
        rows.append({"id":case["id"],"original_step":results[0],"improved_step":improved,"passed":passed})
    args.output.write_text(json.dumps({"rows":rows,"passed":all(row["passed"] for row in rows),
        "install":install,"scope":"七个解析点三角形CCD控制，厚度0；非完整网格连续碰撞证书"},ensure_ascii=False,indent=2),encoding="utf-8")
