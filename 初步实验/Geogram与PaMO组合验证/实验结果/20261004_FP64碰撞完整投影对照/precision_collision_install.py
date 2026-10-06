"""在隔离副本中替换点三角形计算，同时覆盖检测、碰撞能量与CCD核。"""
import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys
import warp as wp


def install_precision_collision():
    """不写作者安装目录；副本仅替换函数导入，边边计算与原算法循环保留。"""
    energy=importlib.import_module("pamo_safe_project.energy")
    output=Path(__file__).with_name("author_precision_snapshots")
    output.mkdir(exist_ok=True)
    rows=[]
    replaced=[]
    modules=["pamo_safe_project.kernels.energy_kernels.collision_energy",
        "pamo_safe_project.kernels.energy_kernels.contact_detection","pamo_safe_project.kernels.ccd_kernels"]
    for name in modules:
        original=importlib.import_module(name)
        source=Path(original.__file__).read_text(encoding="utf-8")
        marker="\n@wp."
        if marker not in source:
            raise ValueError("作者核函数导入与定义结构不符")
        prefix,body=source.split(marker,1)
        modified=prefix+"\nfrom robust_pt_gpu import robust_pt_classify as pt_pair_classify, robust_pt_distance as pt_pair_distance\n"+marker+body
        target=output/(name.split('.')[-1]+"_precision.py")
        target.write_text(modified,encoding="utf-8")
        identity=name.rsplit('.',1)[0]+".precision_"+name.split('.')[-1]
        spec=importlib.util.spec_from_file_location(identity,target)
        clone=importlib.util.module_from_spec(spec)
        sys.modules[identity]=clone
        spec.loader.exec_module(clone)
        changed=[]
        for key,value in vars(original).items():
            if isinstance(value,wp.Kernel) and getattr(energy,key,None) is value:
                setattr(energy,key,getattr(clone,key))
                changed.append(key)
                replaced.append(key)
        rows.append({"original_module":name,"original_sha256":hashlib.sha256(source.encode()).hexdigest(),
            "isolated_sha256":hashlib.sha256(modified.encode()).hexdigest(),"replaced_kernels":changed})
    required={"collision_energy_kernel","collision_diff_kernel","collision_hess_dx_kernel",
        "detect_pt_contact_bvh_kernel","accd_kernel"}
    if not required.issubset(replaced):
        raise ValueError("精度替换没有覆盖完整检测、能量、导数和CCD入口")
    return {"modules":rows,"required_kernels_covered":True,
        "scope":"FP32状态和原浮点导数不变；点三角形分类及距离使用FP64中间量；边边与完整CCD流程保留"}
