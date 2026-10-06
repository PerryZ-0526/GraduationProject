"""在FP64阶段入口安装后固定目标面倍率4，其他完整阶段及参数保持。"""

import pamo


def install_simplification_budget_ratio(value):
    if value != 4:
        raise ValueError("本次完整反馈只冻结倍率4")
    original = pamo.PaMO.run

    def run(self, points, triangles, ratio, *args, **kwargs):
        # 原完整调用仍传倍率1；只将简化目标改为输入面数四倍，不绕过投影。
        if ratio != 1.:
            raise ValueError("原完整调用的倍率已改变")
        return original(self, points, triangles, value, *args, **kwargs)

    pamo.PaMO.run = run
