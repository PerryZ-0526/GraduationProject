"""从已绑定的作者副本生成隔离FP64三角输入候选，保留原FP32场与符号填充。"""

import hashlib
import json
from pathlib import Path
import re
from datetime import datetime, timezone, timedelta


def main():
    source = Path("D:/GraduationProject_切削排斥证据/20261005_作者SDF扩展源码只读核查")
    target = Path("初步实验/Geogram与PaMO切削排斥冻结_20261005_FP64三角输入SDF候选")
    target.mkdir(exist_ok=False)
    manifest = json.loads((source / "01-作者SDF源码摘要绑定.json").read_text("utf8"))
    rows = []
    for row in manifest["files"]:
        name = row["file"]
        data = (source / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("作者副本摘要变化")
        text = data.decode("utf8")
        # 只提升三角形几何计算，原阈值及符号传播保持不变，后续必须单独验证。
        if name == "geometry.cuh":
            text = re.sub(r"\bfloat\b", "double", text).replace("float3", "double3").replace("make_float3", "make_double3").replace("fminf", "fmin")
            text = '// 三角形距离与射线求交使用双精度，保留作者原有判定阈值。\n' + text
        if name in ("rasterize.cuh", "grid.cuh", "sign.cuh"):
            text = text.replace("float3", "double3").replace("make_float3", "make_double3")
        if name == "rasterize.cuh":
            for variable in ("thresh", "finalDist", "rayth"):
                text = text.replace("const float " + variable, "const double " + variable)
            text = '// 三角坐标及局部距离保留FP64，场存储与原子最小值仍为FP32。\n' + text
        if name == "commons.cuh":
            text = text.replace('#include "helper_math.h"', '#include "helper_math.h"\n#include "double_geometry_math.cuh"')
        if name == "torchcumesh2sdf.cu":
            text = text.replace('(float3*)tris.data_ptr<float>()', '(double3*)tris.data_ptr<double>()').replace('"torchcumesh2sdf"', '"cut_sdf_fp64"')
            text = '// 独立扩展只接收连续CUDA FP64三角数组，不在接口降精度。\n' + text
            text = text.replace('    assert(tris.sizes()[1] == 3);', '    TORCH_CHECK(tris.is_cuda() && tris.is_contiguous() && tris.scalar_type() == at::kDouble && tris.dim() == 3, "需要连续CUDA FP64三角数组");\n    assert(tris.sizes()[1] == 3);')
        (target / name).write_text(text, "utf8")
        rows.append({"file": name, "author_sha256": row["sha256"], "sha256": hashlib.sha256((target / name).read_bytes()).hexdigest()})
    # 使用独立向量运算，保留作者原helper中的整数及FP32场运算。
    math = '''#pragma once
// 双精度几何向量运算，仅用于输入三角形与网格查询位置。
inline __host__ __device__ double3 operator+(double3 a,double3 b){return make_double3(a.x+b.x,a.y+b.y,a.z+b.z);}
inline __host__ __device__ double3 operator-(double3 a,double3 b){return make_double3(a.x-b.x,a.y-b.y,a.z-b.z);}
inline __host__ __device__ double3 operator+(double3 a,double b){return make_double3(a.x+b,a.y+b,a.z+b);}
inline __host__ __device__ double3 operator*(double3 a,double b){return make_double3(a.x*b,a.y*b,a.z*b);}
inline __host__ __device__ double3 operator*(double a,double3 b){return b*a;}
inline __host__ __device__ double3 operator/(double3 a,double b){return a*(1.0/b);}
inline __host__ __device__ void operator-=(double3 &a,double3 b){a=a-b;}
inline __host__ __device__ double dot(double3 a,double3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
inline __host__ __device__ double3 cross(double3 a,double3 b){return make_double3(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x);}
inline __host__ __device__ double3 normalize(double3 a){return a/sqrt(dot(a,a));}
inline __host__ __device__ double clamp(double a,double lo,double hi){return fmin(fmax(a,lo),hi);}
inline __host__ __device__ double3 lerp(double3 a,double3 b,double t){return a+(b-a)*t;}
'''
    (target / "double_geometry_math.cuh").write_text(math, "utf8")
    build = '''"""在指定私有目录构建独立扩展，不安装到作者环境。"""
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
'''
    (target / "build_fp64_sdf.py").write_text(build, "utf8")
    for name in ("double_geometry_math.cuh", "build_fp64_sdf.py"):
        rows.append({"file": name, "sha256": hashlib.sha256((target / name).read_bytes()).hexdigest()})
    report = {"生成时间": datetime.now(timezone(timedelta(hours=8))).isoformat(), "修改时间及修改内容": "首次生成，作者摘要绑定的隔离候选", "文档概述": "未运行数值验证，原阈值、符号传播和FP32场不变，禁用fast-math", "索引目录": ["files"], "files": rows}
    (target / "01-隔离候选源码冻结.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf8")
    print(target)


if __name__ == "__main__":
    main()
