"""固定薄壁首刀实际FP64场源，两分辨率两偏移的第一阶段因果诊断。"""
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta
import numpy as np
import torch
import trimesh


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    cfg = json.loads((root / 'inputs.json').read_text('utf8'))
    for name in ('source.obj', 'normalized.obj'):
        if sha(root / name) != cfg['sha256'][name]:
            raise ValueError('固定输入摘要变化')
    ext = cfg['sorted_extension']
    if sha(ext['extension']) != ext['extension_sha256']:
        raise ValueError('排序扩展变化')
    spec = importlib.util.spec_from_file_location(ext['module'], ext['extension'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules['pamo._C'] = module
    import pamo
    if sha(inspect.getfile(pamo.PaMO)) != '0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a':
        raise ValueError('作者阶段源码变化')
    extension = '/root/autodl-tmp/graduation_project/cut_sdf_fp64_20261005_01/build/cut_sdf_fp64.so'
    if sha(extension) != '7388625beeb38be480f8d78faeb724e6797b063e813f2cd69c9c53598d1b9bf2':
        raise ValueError('FP64扩展变化')
    sys.path.insert(0, str(Path(extension).parent))
    import cut_sdf_fp64
    source = trimesh.load(root / 'source.obj', force='mesh', process=False)
    normalized_mesh = trimesh.load(root / 'normalized.obj', force='mesh', process=False)
    origin = np.asarray(cfg['origin_mm'], np.float64)
    local = source.copy()
    local.vertices = np.asarray(source.vertices, np.float64) - origin
    points = torch.from_numpy(np.asarray(local.vertices, np.float32)).cuda()
    faces = torch.from_numpy(np.asarray(local.faces, np.int32)).cuda()
    model = pamo.PaMO(local, use_stage1=True, use_stage3=False)
    _, minimum, maximum, mean = model.preprocess_mesh(points, faces, model.band, model.margin)
    n = np.asarray(points.cpu().numpy(), np.float64)[faces.cpu().numpy()]
    n = ((n - np.asarray(mean, np.float64) - np.asarray(minimum, np.float64)) / float(maximum) + float(model.band)) / float(model.margin)
    from normalized_sdf_chain import canonical_normalized_chain
    _, _, normalized, chain = canonical_normalized_chain(n)
    if not np.array_equal(normalized, normalized_mesh.vertices[normalized_mesh.faces]):
        raise ValueError('实际场源重建不逐位一致')
    checker = '/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646'
    if sha(checker) != '0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3':
        raise ValueError('完整检查器变化')
    check = json.loads(subprocess.run([checker, str(root / 'normalized.obj')], check=True, capture_output=True, text=True).stdout)
    if not check['embedded_closed']:
        raise ValueError('场源不合法')
    out = root / 'result'
    out.mkdir(exist_ok=False)
    report = {'生成时间': datetime.now(timezone(timedelta(hours=8))).isoformat(), '修改时间及修改内容': '首次生成，薄壁同源两分辨率两偏移',
              '文档概述': '不运行简化投影，不直接发布，四网格共用两场', '索引目录': ['parameters', 'fields', 'rows'],
              'inputs': cfg, 'parameters': {'minimum_mm': minimum.tolist(), 'maximum_span_mm': float(maximum), 'mean_mm': mean.tolist(),
                                          'band': model.band, 'margin': model.margin}, 'fields': [], 'rows': [],
              'normalized_array_bitwise_bound': True, 'chain': chain, 'SDF_calls': 2, 'full_PaMO_calls': 0}
    for R in (128, 256):
        # 分辨率不改变冻结归一化几何及原band，偏移对照共用本次实际场。
        model.R = R
        field = cut_sdf_fp64.get_sdf(torch.from_numpy(normalized).cuda(), R, model.band)
        torch.cuda.synchronize()
        a = field.cpu().numpy()
        if not np.isfinite(a).all():
            raise ValueError('场非有限')
        path = out / f'{R}-实际GPU场.npz'
        np.savez_compressed(path, sdf=a)
        report['fields'].append({'R': R, 'file': path.name, 'sha256': sha(path), 'negative_cells': int((a < 0).sum())})
        for offset in (0., .9):
            vertices, triangles = model.vol2mesh(field - offset / R, return_quads=False)
            v = vertices.cpu().numpy()
            # 按作者FP32逆变换及输出均值恢复，最后FP64加世界计算原点。
            v = (((v * R + .5) / (R + 1) * model.margin - model.band) * maximum + minimum)
            v = np.asarray(v, np.float32) + mean
            mesh = trimesh.Trimesh(np.asarray(v, np.float64) + origin, triangles.cpu().numpy(), process=False)
            path = out / f'{R}-偏移{offset}-第一阶段.obj'
            with path.open('w', encoding='utf8') as stream:
                for point in mesh.vertices:
                    stream.write('v ' + ' '.join(format(float(x), '.17g') for x in point) + '\n')
                for face in mesh.faces:
                    stream.write('f ' + ' '.join(str(int(x) + 1) for x in face) + '\n')
            embedding = json.loads(subprocess.run([checker, str(path)], check=True, capture_output=True, text=True).stdout)
            report['rows'].append({'R': R, 'offset': offset, 'file': path.name, 'sha256': sha(path), 'embedding': embedding,
                                   'volume_mm3': float(mesh.volume), 'bounds_mm': mesh.bounds.tolist(),
                                   'components': len(mesh.split(only_watertight=False)), 'euler': int(mesh.euler_number)})
    (out / '01-薄壁同源第一阶段四配置诊断.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    print([(x['R'], x['offset'], x['volume_mm3'], x['embedding']['embedded_closed']) for x in report['rows']], flush=True)


if __name__ == '__main__':
    main()
