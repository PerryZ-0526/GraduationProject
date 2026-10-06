"""作者ODC的CPU材料查询适配，不改变作者提取算法。"""
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from material_state import initial_field, capsule_field


def extract_author(torch, extractor, field, axis, knots, body, source):
    spacing = float(axis[1] - axis[0])
    interpolator = RegularGridInterpolator((axis, axis, axis), field, bounds_error=True)
    counts = {'calls': 0, 'points': 0}

    def implicit(points):
        # 两种查询权限明确分开：格点插值不能借用解析扫掠的额外信息。
        array = points.detach().cpu().numpy()
        if source == 'grid':
            value = interpolator(array)
        else:
            value = initial_field(array, body)
            for start, end in zip(knots[:-1], knots[1:]):
                value = np.maximum(value, -capsule_field(array, start, end, .4))
            value = np.clip(value, -2 * spacing, 2 * spacing)
        counts['calls'] += 1
        counts['points'] += len(array)
        return torch.from_numpy(np.asarray(value, dtype=np.float64))

    vertices, faces = extractor.extract_mesh(implicit, min_coord=[float(axis[0])] * 3,
                                             max_coord=[float(axis[-1])] * 3,
                                             num_grid=len(axis) - 1, batch_size=1000000)
    return vertices.cpu().numpy(), faces.cpu().numpy().reshape(-1, 3), {
        'query_source': source, 'query_counts': counts, 'batch_size': 1000000,
        'num_grid': len(axis) - 1, 'other_parameters': '作者默认参数',
        'torch_default_dtype': str(torch.get_default_dtype()), 'author_algorithm_modified': False}
