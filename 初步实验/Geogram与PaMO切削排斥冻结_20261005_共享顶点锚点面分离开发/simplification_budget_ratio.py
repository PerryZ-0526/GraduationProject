"""按独立累计目标面数限制简化目标，保留旧四倍输入预算作为上限。"""
import json
import math


def target_budget(input_faces, reference_faces):
    if input_faces <= 0 or reference_faces <= 0:
        raise ValueError('源与独立目标都必须有三角面')
    target = min(4 * input_faces, 4 * reference_faces)
    ratio = target / input_faces
    # 对齐作者int(ratio * 面数)，避免整数目标因浮点舍入少一个面。
    if int(ratio * input_faces) < target:
        ratio = math.nextafter(ratio, math.inf)
    if int(ratio * input_faces) != target or ratio > 4:
        raise ValueError('作者浮点倍率不能精确表达当前整数目标')
    return target, ratio


def install_simplification_budget_ratio(value, reference_faces):
    import pamo
    if value != 4:
        raise ValueError('本候选固定目标复杂度倍率4')
    original = pamo.PaMO.run

    def run(self, points, triangles, ratio, *args, **kwargs):
        # 完整作者入口维持原参数，只改变作者简化目标面数，不跳过后续投影。
        if ratio != 1. or kwargs.get('min_verts') != 0:
            raise ValueError('要求原完整倍率1和显式min_verts=0')
        target, actual_ratio = target_budget(len(triangles), reference_faces)
        print(json.dumps({'reference_face_budget': {'input_faces': len(triangles), 'reference_faces': reference_faces,
                         'target_faces': target, 'actual_ratio': actual_ratio}}), flush=True)
        return original(self, points, triangles, actual_ratio, *args, **kwargs)

    pamo.PaMO.run = run
