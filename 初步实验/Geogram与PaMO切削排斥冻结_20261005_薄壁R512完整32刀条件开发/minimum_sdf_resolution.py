"""隔离第一阶段采用统一最低网格分辨率，保持band、偏移与后续阶段。"""


def install_minimum_sdf_resolution(resolution=512):
    if resolution != 512:
        raise ValueError('本开发候选固定最低分辨率512')
    import pamo
    original = pamo.PaMO.remesh

    def remesh(self, *args, **kwargs):
        # 原作者按目标面数降至128或64时仍保留512，不按形状切换偏移。
        self.R = max(self.R, resolution)
        return original(self, *args, **kwargs)

    pamo.PaMO.remesh = remesh
