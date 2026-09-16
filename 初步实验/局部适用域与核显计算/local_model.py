"""以原始分片线性骨面在刀具足迹包围盒中的上界收紧适用性判据。"""
from pathlib import Path
import sys
from time import perf_counter
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]/'边界过渡带联合重建'))
from dynamic import JointPatch
from joint import Rejected
from surface_patch import clip_polygon, triangle_height


def footprint_ceiling(triangles, tool):
    """矩形是胶囊足迹的超集；仿射高度在裁剪多边形顶点取得最大值。"""
    if tool.radius <= 0 or not np.all(np.isfinite([*tool.start, *tool.end, tool.radius, tool.z])):
        raise Rejected('工具参数不合法')
    low = np.minimum(tool.start, tool.end)-tool.radius-1e-10
    high = np.maximum(tool.start, tool.end)+tool.radius+1e-10
    rectangle = np.array([low, [high[0], low[1]], high, [low[0], high[1]]])
    xy = triangles[:, :, :2]
    selected = np.all(xy.max(axis=1) >= low, axis=1) & np.all(xy.min(axis=1) <= high, axis=1)
    values = []
    for triangle in triangles[selected]:
        polygon = clip_polygon(triangle[:, :2], rectangle)
        if len(polygon):
            values.append(float(triangle_height(triangle, polygon).max()))
    if not values:
        raise Rejected('工具足迹不与已验证图域相交，本实验不处理域外事件')
    return max(values)+1e-9


class LocalPatch(JointPatch):
    """历史足迹联合上界；保留原质量、边界与误差证书，不处理倒扣。"""
    def update(self, tool):
        started = perf_counter()
        saved = self.ceiling
        before = len(self.attempts)
        local = None
        try:
            tools = [*self.tools, tool]
            triangles = self.chart.surface.mesh.triangles[self.chart.ids]
            local = max(footprint_ceiling(triangles, item) for item in tools)
            if any(item.z <= local for item in tools):
                raise Rejected('球心未高于历史足迹联合上界，拒绝高度图更新')
            self.ceiling = local
            return super().update(tool)
        except Rejected as exc:
            if len(self.attempts) == before:
                self.attempts.append(dict(step=len(self.tools)+1, accepted=False,
                                          tool=tool.__dict__, reason=str(exc)))
            raise
        finally:
            self.ceiling = saved
            self.attempts[-1].update(local_ceiling_mm=local, global_ceiling_mm=saved,
                                    local_update_ms=(perf_counter()-started)*1000)
