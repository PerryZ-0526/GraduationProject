"""在指定私有目录构建独立扩展，不安装到作者环境。"""
import os,sys,json,hashlib
from pathlib import Path
from datetime import datetime,timezone,timedelta
os.environ["MAX_JOBS"]="1"
os.environ["TORCH_CUDA_ARCH_LIST"]="8.9"
from torch.utils.cpp_extension import load
p=Path(__file__).resolve().parent
b=p/"build";b.mkdir(exist_ok=True)
# 禁用fast-math以保留几何双精度；与原版的差异必须由同编译配置控制核查。
m=load(name="cut_sdf_fp64",sources=[str(p/"torchcumesh2sdf.cu"),str(p/"binding.cpp")],build_directory=str(b),extra_cflags=["-O3","-std=c++17"],extra_cuda_cflags=["-O3","-std=c++17"],verbose=True)
r={"生成时间":datetime.now(timezone(timedelta(hours=8))).isoformat(),"修改时间及修改内容":"首次生成，隔离构建终态","文档概述":"编译成功不等于数值验证通过","索引目录":["extension"],"extension":m.__file__,"extension_sha256":hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()}
(p/"02-隔离扩展构建终态.json").write_text(json.dumps(r,ensure_ascii=False,indent=2),"utf8")
print(json.dumps(r,ensure_ascii=False))
