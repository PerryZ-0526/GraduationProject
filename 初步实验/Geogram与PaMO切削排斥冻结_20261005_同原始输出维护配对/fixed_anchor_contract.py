"""追加固定几何锚点只允许首次求导且CUDA坐标与初态逐位一致。"""
import numpy as np


def promote_fixed_mask(current, requested, positions, encoded_initial, diff_call):
    current = np.asarray(current, bool)
    requested = np.asarray(requested, bool)
    if requested.shape != current.shape or positions.shape != encoded_initial.shape or len(positions) != len(current):
        raise ValueError("固定几何锚点形状不符")
    if np.any(current & ~requested):
        raise ValueError("不能解除已绑定固定几何")
    added = np.flatnonzero(requested & ~current)
    if len(added) and (diff_call != 1 or not np.array_equal(positions[added], encoded_initial[added])):
        raise ValueError("追加固定几何必须在首次求导且坐标未移动")
    return requested.copy(), added
