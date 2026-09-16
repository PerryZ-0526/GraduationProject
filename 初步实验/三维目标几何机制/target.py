"""三维裁剪扫掠的符号场参照；不是距离证书或网格生成算法。"""
import numpy as np


def cut_field(points, item):
    """负值表示胶囊与有限计划圆柱的交集内部，长度单位为mm。"""
    points = np.asarray(points, dtype=np.float64)
    a, b = np.asarray(item['start']), np.asarray(item['end'])
    direction = b-a
    squared = float(direction @ direction)
    # 零长段表示球体，不能除以零或静默丢弃这一磨削状态。
    t = np.clip((points-a) @ direction / squared, 0, 1) if squared else np.zeros(len(points))
    capsule = np.linalg.norm(points-a-t[:, None]*direction, axis=1)-item['radius']
    cylinder = np.maximum(np.linalg.norm(points[:, :2], axis=1)-item['clip_radius'],
                          np.abs(points[:, 2])-20.)
    return np.maximum(capsule, cylinder)


def update_field(previous, points, item):
    """在不反馈离散网格的条件下累积差集；输入是初始实体的负内正外场。"""
    return np.maximum(previous, -cut_field(points, item))


def box_field(points, half_size):
    """解析盒子的符号场用于独立机制测试，不冒充真实骨面。"""
    return np.max(np.abs(points)-np.asarray(half_size), axis=1)
