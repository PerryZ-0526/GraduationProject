"""同一CUDA核对拍原分类距离与FP64中间计算，原输入保持FP32。"""
import argparse
import json
from pathlib import Path
import numpy as np
import warp as wp
from pamo_safe_project.kernels.distance_kernels.distance_kernels import pt_pair_classify,pt_pair_distance
from robust_pt_gpu import robust_pt_classify,robust_pt_distance


@wp.kernel
def query_kernel(points:wp.array(dtype=wp.vec3,ndim=2),types:wp.array(dtype=int,ndim=2),distances:wp.array(dtype=float,ndim=2)):
    i=wp.tid()
    p=points[i,0]
    a=points[i,1]
    b=points[i,2]
    c=points[i,3]
    original=pt_pair_classify(p,a,b,c)
    improved=robust_pt_classify(p,a,b,c)
    types[i,0]=original
    types[i,1]=improved
    distances[i,0]=pt_pair_distance(p,a,b,c,original)
    distances[i,1]=robust_pt_distance(p,a,b,c,improved)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    cases=json.loads(args.inputs.read_text(encoding="utf-8"))["cases"]
    values=np.array([c["positions_normalized"] for c in cases],dtype=np.float32)
    wp.init()
    points=wp.array(values,dtype=wp.vec3,device="cuda:0")
    types=wp.zeros((len(cases),2),dtype=int,device="cuda:0")
    distances=wp.zeros((len(cases),2),dtype=float,device="cuda:0")
    wp.launch(query_kernel,dim=len(cases),inputs=[points],outputs=[types,distances],device="cuda:0")
    wp.synchronize_device("cuda:0")
    result={"types":types.numpy().tolist(),"distances":distances.numpy().tolist(),
        "scope":"CUDA逐查询分类和距离；非完整求解、导数或CCD验证"}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
