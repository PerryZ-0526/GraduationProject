"""生成独立CUDA算子副本，仅为作者折叠增加固定顶点拒绝条件。"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("源码锚点不唯一: " + old[:60])
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    source = ROOT / "reference/近期强基线_20260908/pamo/simp_cuda/src"
    dst = args.output / "src"
    shutil.copytree(source, dst)
    record = {"source_sha256": {}, "variant_sha256": {}}
    for name in ("cusimp_free.h", "cusimp_free.cu", "pybind.cpp"):
        text = (source / name).read_text(encoding="utf-8")
        record["source_sha256"][name] = hashlib.sha256(text.encode()).hexdigest()
        if name == "cusimp_free.h":
            text = replace_once(text, "    float tres{};", "    // 固定掩码由调用者持有，与当前输入顶点顺序一致。\n    const int* fixed_vertices{};\n    float tres{};")
        elif name == "cusimp_free.cu":
            text = replace_once(text, "        int idx_v1 = edge.v;", "        int idx_v1 = edge.v;\n\n        // 任一端点固定就禁折叠，保证外部面的几何与连接不受操作影响。\n        if (sp.fixed_vertices && (sp.fixed_vertices[idx_v0] || sp.fixed_vertices[idx_v1])) {\n            sp.edge_cost[edge_index] = std::numeric_limits<uint32_t>::max();\n            return;\n        }")
        else:
            text = replace_once(text, "    CUSimp_Free pamo;", "    CUSimp_Free pamo;\n    // 持有张量以保证核函数访问期间掩码内存有效。\n    torch::Tensor fixed_tensor;")
            text = replace_once(text, "public:\n    ~CUDSP_Free()", "public:\n    void set_fixed_mask(torch::Tensor mask) {\n      CHECK_INPUT(mask);\n      TORCH_CHECK(mask.scalar_type() == torch::kInt && mask.dim() == 1, \"fixed mask must be int32 vector\");\n      fixed_tensor = mask;\n      pamo.fixed_vertices = mask.data_ptr<int>();\n    }\n\n    ~CUDSP_Free()")
            # 只修改带固定掩码的类，不触及作者另一个简化类的同名局部变量。
            anchor = "      int nPts = points.size(0);"
            if text.count(anchor) != 2:
                raise ValueError("两类顶点数量锚点与固定源码不一致")
            text = text.replace(anchor, anchor + "\n      // 当前顶点重编号后必须同步更新固定掩码。\n      TORCH_CHECK(!fixed_tensor.defined() || fixed_tensor.numel() == nPts, \"fixed mask size mismatch\");", 1)
            text = replace_once(text, "  pybind11::class_<cusimp_free::CUDSP_Free>(m, \"CUDSP_Free\")\n      .def(py::init<>())", "  pybind11::class_<cusimp_free::CUDSP_Free>(m, \"CUDSP_Free\")\n      .def(py::init<>())\n      .def(\"set_fixed_mask\", &cusimp_free::CUDSP_Free::set_fixed_mask)")
            # 模块内注册允许隔离扩展与原版PaMO在同一CPU预加载进程共存。
            text = replace_once(text, "(m, \"CUDSP_Free\")", "(m, \"CUDSP_Free\", py::module_local())")
            text = replace_once(text, "(m, \"CUDSP\")", "(m, \"CUDSP\", py::module_local())")
        (dst / name).write_text(text, encoding="utf-8", newline="\n")
        record["variant_sha256"][name] = hashlib.sha256((dst / name).read_bytes()).hexdigest()
    (args.output / "01-CUDA固定掩码源码记录.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with tarfile.open(args.output / "locality_cuda.tar.gz", "w:gz") as archive:
        archive.add(dst, arcname="src")
    print("独立CUDA副本已生成")


if __name__ == "__main__":
    main()
