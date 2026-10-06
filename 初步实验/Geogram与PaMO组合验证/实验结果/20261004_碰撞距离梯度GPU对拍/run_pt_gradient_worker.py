"""对拍已修正分类下的作者距离梯度，保留零距离和退化查询原输出。"""
import argparse
import json
from pathlib import Path
import numpy as np
import warp as wp
from robust_pt_gpu import robust_pt_classify
from pamo_safe_project.kernels.distance_kernels.distance_kernels_struct import pt_pair_distance_grad_struct


@wp.kernel
def gradient_kernel(points:wp.array(dtype=wp.vec3,ndim=2),gradients:wp.array(dtype=wp.vec3,ndim=2)):
    i=wp.tid()
    p=points[i,0]
    a=points[i,1]
    b=points[i,2]
    c=points[i,3]
    kind=robust_pt_classify(p,a,b,c)
    gradient=pt_pair_distance_grad_struct(p,a,b,c,kind)
    gradients[i,0]=gradient.d0
    gradients[i,1]=gradient.d1
    gradients[i,2]=gradient.d2
    gradients[i,3]=gradient.d3


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    cases=json.loads(args.inputs.read_text(encoding="utf-8"))["cases"]
    wp.init()
    points=wp.array(np.array([case["positions_normalized"] for case in cases],np.float32),dtype=wp.vec3,device="cuda:0")
    gradients=wp.zeros((len(cases),4),dtype=wp.vec3,device="cuda:0")
    wp.launch(gradient_kernel,dim=len(cases),inputs=[points],outputs=[gradients],device="cuda:0")
    wp.synchronize_device("cuda:0")
    args.output.write_text(json.dumps({"gradients":gradients.numpy().tolist(),
        "scope":"作者FP32梯度使用新分类；光滑有效查询另由独立参照筛选"},ensure_ascii=False,indent=2),encoding="utf-8")
