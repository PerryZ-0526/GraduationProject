"""在隔离副本中为两条已定位的漏边添加只读 CUDA 打印。"""

import argparse
import hashlib
from pathlib import Path
import shutil


SOURCE_SHA256 = "0d19bbe0c6a23509a2927d16a6d0d5a8909d032a34ea87fa9f5df4742a8ce917"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    original = args.source / "rasterize.cuh"
    if hashlib.sha256(original.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("源文件摘要与已冻结版本不一致")
    shutil.copytree(args.source, args.destination,
                    ignore=shutil.ignore_patterns(".git", "build", "*.egg-info", "*.so"))
    target = args.destination / "rasterize.cuh"
    content = target.read_text(encoding="utf-8")
    predicate = (
        "((tofs == 2032 && nxyz.x == 175 * N / 256 && nxyz.y == 175 * N / 256 "
        "&& nxyz.z == 48 * N / 256) || "
        "(tofs == 3703 && nxyz.x == 151 * N / 256 && nxyz.y == 151 * N / 256 "
        "&& nxyz.z == 47 * N / 256))"
    )
    old_layer = "const bool intersect = point_to_tri_dist_sqr(v1, v2, v3, fxyz) < thresh * thresh;"
    new_layer = (
        "const float debugDistSqr = point_to_tri_dist_sqr(v1, v2, v3, fxyz);\n"
        "    const bool intersect = debugDistSqr < thresh * thresh;\n"
        f"    if ({predicate})\n"
        "        printf(\"DBG_LAYER N=%d face=%u xyz=%u,%u,%u dist=%g threshold=%g chosen=%d\\n\", "
        "N, tofs, nxyz.x, nxyz.y, nxyz.z, sqrtf(debugDistSqr), thresh, intersect);"
    )
    if content.count(old_layer) != 1:
        raise ValueError("层级栅格化替换点不唯一")
    content = content.replace(old_layer, new_layer)
    old_reduce = "const float finalDist = sqrt(point_to_tri_dist_sqr(v1, v2, v3, fxyz));"
    new_reduce = (
        old_reduce + "\n"
        f"    if ({predicate})\n"
        "        printf(\"DBG_REDUCE face=%u xyz=%u,%u,%u dist=%g ray_z=%g\\n\", "
        "tofs, nxyz.x, nxyz.y, nxyz.z, finalDist, "
        "ray_triangle_hit_dist(v1, v2, v3, fxyz, make_float3(0, 0, 1), finalDist));\n"
        f"    if ({predicate}) {{\n"
        "        const float3 e1 = v2 - v1;\n"
        "        const float3 e2 = v3 - v1;\n"
        "        const float3 o = fxyz - v1;\n"
        "        const float3 ray = make_float3(0, 0, 1);\n"
        "        const float3 cr = cross(ray, e2);\n"
        "        const float det = dot(cr, e1);\n"
        "        const float u = dot(o, cr) / det;\n"
        "        const float3 scr = cross(o, e1);\n"
        "        const float v = dot(ray, scr) / det;\n"
        "        const float t = dot(e2, scr) / det;\n"
        "        printf(\"DBG_PRED face=%u det=%g u=%.10g v=%.10g t=%g epsilon=%g\\n\", "
        "tofs, det, u, v, t, FLT_EPSILON);\n"
        "    }"
    )
    if content.count(old_reduce) != 1:
        raise ValueError("最终栅格化替换点不唯一")
    content = content.replace(old_reduce, new_reduce)
    target.write_text(content, encoding="utf-8")
    print(hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
