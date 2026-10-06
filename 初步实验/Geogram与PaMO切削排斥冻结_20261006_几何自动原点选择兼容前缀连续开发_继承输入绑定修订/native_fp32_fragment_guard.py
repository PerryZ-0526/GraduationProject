"""隔离修复入口对齐实际FP32面积运算，不改共享作者或旧实验函数。"""

import numpy as np

import fragment_pipeline
import locality_retriangulate
import locality_sliver_collapse


original_invalid_faces = locality_retriangulate.invalid_faces


def native_fp32_invalid_faces(vertices, faces):
    """保留原判定，另加入原生FP32叉积及范数为零的真实运算负例。"""
    result = original_invalid_faces(vertices, faces)
    triangles = np.asarray(vertices, dtype=np.float32)[faces]
    area2 = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0],
                                    triangles[:, 2] - triangles[:, 0]), axis=1)
    return result | (area2 == 0) | ~np.isfinite(area2)


def repair_input_native_fp32(mesh, bits, **kwargs):
    """只在本次既有修复调用中替换检测器，所有链接、来源与几何约束不变。"""
    modules = (fragment_pipeline, locality_retriangulate, locality_sliver_collapse)
    previous = [module.invalid_faces for module in modules]
    try:
        for module in modules:
            module.invalid_faces = native_fp32_invalid_faces
        candidate, labels, record = fragment_pipeline.repair_input(mesh, bits, **kwargs)
        record.update(native_fp32_arithmetic_guard=True,
                      old_detector_bad_faces=int(original_invalid_faces(mesh.vertices, mesh.faces).sum()),
                      detector_scope="old_thresholds_or_native_FP32_zero_or_nonfinite_area")
        return candidate, labels, record
    finally:
        for module, detector in zip(modules, previous):
            module.invalid_faces = detector
