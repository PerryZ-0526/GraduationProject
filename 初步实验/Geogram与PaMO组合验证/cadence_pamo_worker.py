"""独立CUDA进程运行完整作者PaMO，保留输入输出与进程成本。"""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh
import torch
import pamo
import torchcumesh2sdf


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(exist_ok=False)
    mesh=trimesh.load(args.source,process=False)
    np.random.seed(2026100607);torch.manual_seed(2026100607)
    torch.cuda.synchronize();start=perf_counter()
    # 固定完整三阶段与ratio=1，不减少投影迭代或替换作者安装。
    model=pamo.PaMO(mesh,use_stage1=True,use_stage3=True)
    vertices,faces=model.run(torch.from_numpy(np.asarray(mesh.vertices,dtype=np.float32)).cuda(),
                            torch.from_numpy(np.asarray(mesh.faces,dtype=np.int32)).cuda(),ratio=1.0,min_verts=0)
    torch.cuda.synchronize();elapsed=(perf_counter()-start)*1000
    from locality_masks import save_obj_fp64
    save_obj_fp64(trimesh.Trimesh(vertices,faces,process=False),args.output/'candidate.obj')
    info=dict(pamo_run_ms=elapsed,full_three_stages=True,ratio=1.0,min_verts=0,
              installed_pamo_sha256=hashlib.sha256(Path(pamo.__file__).read_bytes()).hexdigest(),
              extension_sha256=hashlib.sha256(Path(torchcumesh2sdf.__file__).read_bytes()).hexdigest(),
              source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest())
    (args.output/'details.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(info,ensure_ascii=False),flush=True)
