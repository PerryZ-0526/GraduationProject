"""归一化运算使用FP64中间值，最终一次转FP32，不改变作者逆变换参数。"""

import numpy as np


def normalize_initial_once(points, faces, mean, minimum, maximum, band, margin):
    values = np.asarray(points, np.float64)[faces]
    values = ((values - np.asarray(mean, np.float64) - np.asarray(minimum, np.float64)) / float(maximum)
              + float(band)) / float(margin)
    return np.ascontiguousarray(values, np.float32)


def install_single_round_normalization():
    import pamo
    original = pamo.PaMO.preprocess_mesh

    def preprocess(self, points, triangles, band, margin):
        # 保留作者均值、范围及碰撞源计算，先经过已安装的实际CUDA面积保护。
        _, minimum, maximum, mean = original(self, points, triangles, band, margin)
        normalized = normalize_initial_once(points.cpu().numpy(), triangles.cpu().numpy(),
                                            mean, minimum, maximum, band, margin)
        return normalized, minimum, maximum, mean

    pamo.PaMO.preprocess_mesh = preprocess
