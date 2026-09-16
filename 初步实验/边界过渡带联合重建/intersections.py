"""对检测器报警面作精确投影分离复核；无法证明分离的报警仍然拒绝。"""
from fractions import Fraction
from itertools import combinations


def separated_xy(first, second):
    """凸三角形分离轴判据，用输入浮点数的精确有理值计算；接触不判为分离。"""
    a = [[Fraction(float(x)), Fraction(float(y))] for x, y, *_ in first]
    b = [[Fraction(float(x)), Fraction(float(y))] for x, y, *_ in second]
    for polygon in (a, b):
        for i in range(3):
            u, v = polygon[i], polygon[(i+1) % 3]
            axis = [-(v[1]-u[1]), v[0]-u[0]]
            pa = [p[0]*axis[0]+p[1]*axis[1] for p in a]
            pb = [p[0]*axis[0]+p[1]*axis[1] for p in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return True
    return False


def resolve_flags(candidate, audit):
    """仅在所有报警面两两投影严格分离时排除报警，保留原始计数及审计证据。"""
    import numpy as np
    flags = np.flatnonzero(candidate['intersection_flags'])
    triangles = candidate['whole'].triangles
    unresolved = []
    for i, j in combinations(flags, 2):
        if not separated_xy(triangles[i], triangles[j]):
            unresolved.append([int(i), int(j)])
    audit['unresolved_flag_pairs'] = unresolved
    audit['projection_refuted_flags'] = len(flags) if len(flags) >= 2 and not unresolved else 0
    # 单面孤立报警或不确定接触不能忽略；该复核依赖检测器返回完整的报警面集合。
    cleared = not len(flags) or (len(flags) >= 2 and not unresolved)
    audit['accepted'] = bool(cleared and audit['watertight'] and audit['winding'] and
                             audit['euler'] == 2 and not audit['nonmanifold_edges'] and
                             not audit['degenerate'] and not audit['bad_faces'] and
                             audit['error_max_mm'] <= .1 and audit['coverage_max_mm2'] <= 1e-7)
