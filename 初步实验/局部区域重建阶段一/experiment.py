"""多轨迹、多密度解析验证，保存失败与耗时，不以拒绝代替成功。"""
import hashlib
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from time import perf_counter
import numpy as np
import pymeshlab as pm
from patch_model import PatchModel, Sweep, Rejected

BASE = Path(__file__).parent
OUT = BASE/'实验结果'


def cases():
    """平移偏置用于避免所有切削边界恰好落在规则格点上。"""
    offset = .037
    paths = np.linspace(-1.2, 1.2, 9)
    horizontal = [Sweep((a, offset), (b, offset), 2., 1.35) for a, b in zip(paths[:-1], paths[1:])]
    vertical = [Sweep((offset, a), (offset, b), 2., 1.35) for a, b in zip(paths[:-1], paths[1:])]
    repeat = Sweep((-.8, offset), (.8, offset), 2., 1.5)
    return [
        ('浅切', 'plane', [Sweep((a, offset), (b, offset), 2., 1.95) for a, b in zip(paths[:-1], paths[1:])], True),
        ('相切', 'plane', [Sweep((a, offset), (b, offset), 2., 2.) for a, b in zip(paths[:-1], paths[1:])], True),
        ('重复切削', 'plane', [repeat]*12, True),
        ('交叉轨迹', 'plane', horizontal+vertical, True),
        ('近边界但不越界', 'plane', [Sweep((1.8, a/2), (1.8, b/2), 2., 1.5) for a, b in zip(paths[:-1], paths[1:])], True),
        ('球窝交叉', 'bowl', [Sweep((a/2, offset), (b/2, offset), 3., .2) for a, b in zip(paths[:-1], paths[1:])]+
         [Sweep((offset, a/2), (offset, b/2), 3., .2) for a, b in zip(paths[:-1], paths[1:])], True),
        ('陡壁压力', 'plane', [Sweep((0., offset), (0., offset), 2., .02)], False),
        ('越过固定边界', 'plane', [Sweep((3.9, offset), (3.9, offset), 2., 1.5)], False),
        ('倒扣范围外', 'plane', [Sweep((0., offset), (0., offset), 2., -.1)], False),
    ]


def independent_height(xy, kind, tools):
    """独立实现解析距离，用端点及直线垂距分段计算，不调用被测高度函数。"""
    z = np.zeros(len(xy)) if kind == 'plane' else 7.5-np.sqrt(100-xy[:, 0]**2-xy[:, 1]**2)
    for tool in tools:
        ax, ay = tool.start
        bx, by = tool.end
        dx, dy = bx-ax, by-ay
        length2 = dx*dx+dy*dy
        first = (xy[:, 0]-ax)**2+(xy[:, 1]-ay)**2
        last = (xy[:, 0]-bx)**2+(xy[:, 1]-by)**2
        squared = np.minimum(first, last)
        if length2:
            projection = (xy[:, 0]-ax)*dx+(xy[:, 1]-ay)*dy
            interior = (projection >= 0) & (projection <= length2)
            squared[interior] = ((xy[interior, 0]-ax)*dy-(xy[interior, 1]-ay)*dx)**2/length2
        inside = squared < tool.radius*tool.radius
        z[inside] = np.minimum(z[inside], tool.z-np.sqrt(tool.radius*tool.radius-squared[inside]))
    return z


def audit_surface(model, seed=20260907):
    """独立随机查询验证证书，并用另一组件核对最终表面自相交。"""
    rng = np.random.default_rng(seed)
    ids = rng.integers(len(model.faces), size=30000)
    uv = rng.random((len(ids), 2))
    uv[uv.sum(axis=1) > 1] = 1-uv[uv.sum(axis=1) > 1]
    weights = np.column_stack((uv, 1-uv.sum(axis=1)))
    points = np.einsum('fi,fij->fj', weights, model.vertices[model.faces[ids]])
    error = np.abs(points[:, 2]-independent_height(points[:, :2], model.kind, model.tools))
    assert np.all(error <= model.bounds[ids]+1e-12), '独立查询发现证书失效'
    ms = pm.MeshSet()
    ms.add_mesh(pm.Mesh(model.vertices, model.faces))
    ms.compute_selection_by_self_intersections_per_face()
    return dict(mean_mm=float(error.mean()), p95_mm=float(np.percentile(error, 95)),
                p99_mm=float(np.percentile(error, 99)), max_mm=float(error.max()),
                over_01mm=int(np.sum(error > .1)), queries=len(ids), seed=seed,
                self_intersection_faces=ms.current_mesh().selected_face_number())


def main():
    OUT.mkdir(exist_ok=True)
    records = []
    for spacing in (.4, .25, .16):
        for index, (name, kind, tools, expected) in enumerate(cases()):
            start = perf_counter()
            model = PatchModel(spacing, kind)
            init_ms = (perf_counter()-start)*1000
            for tool in tools:
                try:
                    model.update(tool)
                except Rejected:
                    break
            audit = audit_surface(model)
            record = dict(name=name, kind=kind, spacing_mm=spacing, expected_supported=expected,
                          initialization_ms=init_ms, requested_steps=len(tools),
                          accepted_steps=len(model.tools), attempts=model.attempts,
                          final_audit=audit, face_count=len(model.faces))
            records.append(record)
            np.savez_compressed(OUT/f'mesh_{spacing}_{index}.npz', vertices=model.vertices,
                                faces=model.faces, q=model.q, angle=model.angles, bounds=model.bounds)
            print(spacing, index, len(model.tools), '/', len(tools), audit['max_mm'], flush=True)
    data = dict(time_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                parameters=dict(min_angle_deg=25, min_q=.4, max_vertical_error_mm=.1,
                                barycentric_divisions=32, random_samples=30000, seed=20260907),
                code_sha256={name: hashlib.sha256((BASE/name).read_bytes()).hexdigest()
                             for name in ['patch_model.py', 'experiment.py']}, records=records)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    (OUT/'results.json').write_text(text, encoding='utf8')
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S')
    (OUT/f'run_{stamp}.json').write_text(text, encoding='utf8')


if __name__ == '__main__':
    main()
