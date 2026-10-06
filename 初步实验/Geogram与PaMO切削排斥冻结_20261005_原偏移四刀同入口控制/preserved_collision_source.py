"""只为全部固定接触插入原几何分支，其他作者核函数语句原样保留。"""
import ast

PARAMETERS = "    original_fixed: wp.array(dtype=int),\n    original_mm: wp.array(dtype=wp.vec3d),\n    geometry_scale: wp.float64,\n    geometry_failures: wp.array(dtype=int),\n"
ALL_FIXED = "original_fixed[b_indices[bid, 0]] != 0 and original_fixed[b_indices[bid, 1]] != 0 and original_fixed[b_indices[bid, 2]] != 0 and original_fixed[b_indices[bid, 3]] != 0"


def modify_kernel(source, name, branch, marker):
    functions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(functions) != 1:
        raise ValueError("作者目标核函数不唯一："+name)
    node = functions[0]
    lines = source.splitlines(keepends=True)
    start, body, end = node.lineno-1, node.body[0].lineno-1, node.end_lineno
    signature = "".join(lines[start:body])
    if signature.count("):\n") != 1:
        raise ValueError("核函数签名结构变化")
    signature = signature.replace("):\n", PARAMETERS+"):\n")
    original = "".join(lines[body:end])
    if original.count(marker) != 1:
        raise ValueError("固定接触分支位置不唯一")
    changed = original.replace(marker, marker+branch)
    return "".join(lines[:start])+signature+changed+"".join(lines[end:])


def preserve_energy_source(source):
    source = "from fixed_geometry_gpu import preserved_pt_distance, preserved_ee_distance\n"+source
    marker = "    i3 = b_indices[bid, 3]\n"
    energy = f"""
    # 全部固定接触仍保留在列表和能量中，只从保存原几何计算其常量距离。
    if {ALL_FIXED}:
        distance_mm = wp.float64(0.0)
        if b_types[bid, 0] == BlockTypes.PT_CONTACT:
            distance_mm = preserved_pt_distance(original_mm[i0], original_mm[i1], original_mm[i2], original_mm[i3])
        elif b_types[bid, 0] == BlockTypes.EE_CONTACT:
            distance_mm = preserved_ee_distance(original_mm[i0], original_mm[i1], original_mm[i2], original_mm[i3])
        d_fixed = wp.float32(distance_mm*geometry_scale)
        d_[bid] = d_fixed
        if d_fixed <= 0.0 or not wp.isfinite(d_fixed):
            wp.atomic_add(geometry_failures, 0, 1)
        elif d_fixed < d_hat:
            wp.atomic_add(energy, 0, compute_b(d_fixed, d_hat)*kappa)
        return
"""
    source = modify_kernel(source, "collision_energy_kernel", energy, marker)
    diff = f"""
    # 固定接触的受约束导数为零，清空缓存，避免上一接触列表重排后遗留值。
    if {ALL_FIXED}:
        for j in range(4):
            dd_dx_[bid, j] = wp.vec3(0.0)
        return
"""
    source = modify_kernel(source, "collision_diff_kernel", diff, marker)
    hess = f"""
    # 此分支的四个自由度均固定，受约束Hessian向量乘恰为零。
    if {ALL_FIXED}:
        return
"""
    source = modify_kernel(source, "collision_hess_dx_kernel", hess, "    if bid >= counter[0]:\n        return\n")
    return source


def preserve_ccd_source(source):
    source = "from fixed_geometry_gpu import preserved_pt_distance, preserved_ee_distance\n"+source
    branch = f"""
    # 全部固定接触单独验证原几何正距离及严格零速度，不能借静态分支绕过运动约束。
    if {ALL_FIXED}:
        distance_mm = wp.float64(0.0)
        if b_types[bid, 0] == BlockTypes.PT_CONTACT:
            distance_mm = preserved_pt_distance(original_mm[i0], original_mm[i1], original_mm[i2], original_mm[i3])
        elif b_types[bid, 0] == BlockTypes.EE_CONTACT:
            distance_mm = preserved_ee_distance(original_mm[i0], original_mm[i1], original_mm[i2], original_mm[i3])
        if distance_mm <= wp.float64(0.0) or not wp.isfinite(distance_mm):
            wp.atomic_add(geometry_failures, 0, 1)
        if wp.dot(v[i0], v[i0])+wp.dot(v[i1], v[i1])+wp.dot(v[i2], v[i2])+wp.dot(v[i3], v[i3]) != 0.0:
            wp.atomic_add(geometry_failures, 1, 1)
        return
"""
    return modify_kernel(source, "accd_kernel", branch, "    i3 = b_indices[bid, 3]\n")
