"""新候选显式关闭SDF重建；保留旧调用签名用于冻结启动器接入。"""


def install_minimum_sdf_resolution(resolution=640):
    if resolution != 640:
        raise ValueError('旧启动器占位参数改变，当前候选不执行SDF')
    # 原分辨率安装点仅安装作者阶段开关，不执行距离场或设置误差验收线。
    from exact_source_stage23 import install_exact_source_stage23
    install_exact_source_stage23()
