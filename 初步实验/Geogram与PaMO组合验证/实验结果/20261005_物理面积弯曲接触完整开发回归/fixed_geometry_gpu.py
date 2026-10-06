"""固定原始FP64几何上的GPU接触距离，不缩小间隙或设置距离下限。"""
import warp as wp
from robust_pt_gpu import segment_candidate


@wp.func
def preserved_pt_distance(p: wp.vec3d, a: wp.vec3d, b: wp.vec3d, c: wp.vec3d):
    normal = wp.cross(b-a, c-a)
    square = wp.dot(normal, normal)
    # 直接用保存毫米坐标计算，避免先归一化并编码FP32丢失间隙。
    if square > wp.float64(0.0):
        first = wp.dot(wp.cross(b-a, p-a), normal)
        second = wp.dot(wp.cross(c-b, p-b), normal)
        third = wp.dot(wp.cross(a-c, p-c), normal)
        if first >= wp.float64(0.0) and second >= wp.float64(0.0) and third >= wp.float64(0.0):
            numerator = wp.dot(p-a, normal)
            return wp.abs(numerator)/wp.sqrt(square)
    ab = segment_candidate(p, a, b, 3, 1, 2)
    bc = segment_candidate(p, b, c, 6, 2, 4)
    ca = segment_candidate(p, c, a, 5, 4, 1)
    return wp.sqrt(wp.min(ab.square, wp.min(bc.square, ca.square)))


@wp.func
def preserved_ee_distance(a: wp.vec3d, b: wp.vec3d, c: wp.vec3d, d: wp.vec3d):
    acd = segment_candidate(a, c, d, 4, 0, 1)
    bcd = segment_candidate(b, c, d, 5, 2, 3)
    cab = segment_candidate(c, a, b, 6, 0, 2)
    dab = segment_candidate(d, a, b, 7, 1, 3)
    best = wp.min(wp.min(acd.square, bcd.square), wp.min(cab.square, dab.square))
    u = b-a
    v = d-c
    n = wp.cross(u, v)
    determinant = wp.dot(n, n)
    # 用叉积避免近平行时Gram乘积相减；仍是浮点实现，需要精确参考对拍。
    if determinant > wp.float64(0.0):
        s = wp.dot(wp.cross(c-a, v), n)/determinant
        t = wp.dot(wp.cross(c-a, u), n)/determinant
        if s > wp.float64(0.0) and s < wp.float64(1.0) and t > wp.float64(0.0) and t < wp.float64(1.0):
            delta = a+s*u-c-t*v
            best = wp.min(best, wp.dot(delta, delta))
    return wp.sqrt(best)


@wp.kernel
def fixed_geometry_queries(points: wp.array(dtype=wp.vec3d, ndim=2), types: wp.array(dtype=int),
                           distances: wp.array(dtype=wp.float64)):
    i = wp.tid()
    if types[i] == 3:
        distances[i] = preserved_pt_distance(points[i, 0], points[i, 1], points[i, 2], points[i, 3])
    elif types[i] == 4:
        distances[i] = preserved_ee_distance(points[i, 0], points[i, 1], points[i, 2], points[i, 3])


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    import numpy as np
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = np.load(args.queries)
    wp.init()
    device = "cuda:0"
    points = wp.array(data["points"], dtype=wp.vec3d, device=device)
    types = wp.array(data["types"], dtype=int, device=device)
    distances = wp.zeros(len(data["types"]), dtype=wp.float64, device=device)
    wp.launch(fixed_geometry_queries, len(data["types"]), inputs=[points, types], outputs=[distances], device=device)
    wp.synchronize_device(device)
    actual = distances.numpy()
    reference = data["reference"]
    # 误差阈值只用于查询对拍，不替代几何验收或引入碰撞距离下限。
    tolerance = np.maximum(1e-15, np.abs(reference)*1e-6)
    valid = np.isfinite(actual) & (np.abs(actual-reference) <= tolerance)
    valid &= np.where(reference > 0, actual > 0, actual == 0)
    result = dict(device=str(wp.get_device(device)), warp_version=wp.__version__, queries=len(actual),
                  passed=int(valid.sum()), point_dtype="float64", distances_mm=actual.tolist(),
                  maximum_absolute_error_mm=float(np.abs(actual-reference).max()),
                  failed_indices=np.flatnonzero(~valid).tolist(), published=False)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "distances_mm"}))
    if not valid.all():
        raise SystemExit(1)
