"""真实维护域边界上的扫掠必须拒绝，且不得改变已有几何和工具历史。"""
import json
import numpy as np
from experiment import OUT, load_candidate
from local_model import LocalPatch, Rejected
from patch_model import Sweep


if __name__ == '__main__':
    candidate, chart = load_candidate()
    model = LocalPatch(chart, candidate)
    position = tuple(model.xy[model.boundary_edges[0]].mean(axis=0))
    original = model.vertices.copy()
    try:
        model.update(Sweep(position, position, 3., chart.ceiling+.1))
    except Rejected:
        pass
    else:
        raise AssertionError('边界扫掠未被拒绝')
    np.testing.assert_array_equal(model.vertices, original)
    assert not model.tools and model.ceiling == chart.ceiling
    assert '固定边界' in model.attempts[-1]['reason']
    (OUT/'boundary.json').write_text(json.dumps(dict(record=model.attempts[-1], unchanged=True),
                                               ensure_ascii=False, indent=2), encoding='utf-8')
    print(model.attempts[-1])
