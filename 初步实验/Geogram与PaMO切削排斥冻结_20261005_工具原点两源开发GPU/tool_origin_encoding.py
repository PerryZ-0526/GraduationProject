"""隔离完整PaMO的工具原点编码，物理源与工具仍保持原世界坐标。"""

import numpy as np
import torch
import pamo
import locality_gpu


def install_tool_origin(origin):
    origin = np.asarray(origin, dtype=np.float64)
    original_full = locality_gpu.run_full
    original_preprocess = pamo.PaMO.preprocess_mesh
    observations = []

    def preprocess(self, points, triangles, band, margin):
        result = original_preprocess(self, points, triangles, band, margin)
        normalized, _, _, mean = result
        # 实际CUDA碰撞源使用作者再中心化后的坐标，不能只看首次转换。
        centered = points - torch.from_numpy(mean).to(points.device)
        t = centered[triangles.long()]
        area2 = torch.linalg.vector_norm(torch.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0], dim=1), dim=1)
        bad = int(torch.sum((area2 == 0) | ~torch.isfinite(area2)).item())
        n = normalized
        sdf_bad = int(np.sum(np.linalg.norm(np.cross(n[:, 1] - n[:, 0], n[:, 2] - n[:, 0]), axis=1) == 0))
        observations.append({"actual_CUDA_centered_source_zero_or_nonfinite_area": bad,
                             "actual_CPU_normalized_SDF_source_zero_area": sdf_bad})
        if bad:
            raise RuntimeError(f"工具原点编码后实际CUDA再中心化源仍有{bad}个退化面，禁止继续完整求解")
        return result

    def run_full(mesh, use_stage1=True):
        local = mesh.copy()
        local.vertices = np.asarray(mesh.vertices, dtype=np.float64) - origin
        encoded = np.asarray(local.vertices, dtype=np.float32)
        encoding_error = np.linalg.norm(encoded.astype(np.float64) + origin - mesh.vertices, axis=1)
        result, details = original_full(local, use_stage1=use_stage1)
        # 以FP64加回原点，只改变计算表示，不把本地坐标作为世界坐标交付。
        result.vertices = np.asarray(result.vertices, dtype=np.float64) + origin
        details.update(coordinate_encoding="FP64_tool_origin_subtraction_before_FP32",
                       world_origin_mm=origin.tolist(), initial_encoding_max_error_mm=float(encoding_error.max()),
                       coordinate_pipeline_observations=observations,
                       timing_role="diagnostic_with_extra_source_checks_not_fair_speed_benchmark")
        return result, details

    pamo.PaMO.preprocess_mesh = preprocess
    locality_gpu.run_full = run_full
