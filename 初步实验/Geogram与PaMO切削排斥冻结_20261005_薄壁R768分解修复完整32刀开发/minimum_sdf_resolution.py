"""隔离第一阶段采用统一最低网格分辨率，保持band、偏移与后续阶段。"""


def install_minimum_sdf_resolution(resolution=768):
    if resolution != 768:
        raise ValueError('本开发候选固定最低分辨率768')
    import pamo
    original = pamo.PaMO.remesh

    def remesh(self, *args, **kwargs):
        # 原作者按目标面数降至128或64时仍保留768，不按形状切换偏移。
        # 显存保护与同源阶段控制相同，不释放其他进程资源。
        import torch
        free_bytes, _ = torch.cuda.mem_get_info()
        if free_bytes < 12 * (1 << 30):
            raise RuntimeError('R768可用显存不足12GiB，停止本次求解')
        self.R = max(self.R, resolution)
        return original(self, *args, **kwargs)

    pamo.PaMO.remesh = remesh
