"""同一合法FP32几何，比较作者、同配置FP32及同配置FP64的完整GPU场。"""
import hashlib
import json
from pathlib import Path
import sys
import subprocess
from datetime import datetime, timezone, timedelta
import numpy as np
import torch
import trimesh


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'inputs.json').read_text('utf8'))
    import torchcumesh2sdf
    if sha(torchcumesh2sdf.__file__) != 'c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad':
        raise ValueError('作者扩展改变')
    for row in config['extensions']:
        if sha(row['path']) != row['sha256']:
            raise ValueError('控制或候选扩展改变')
        sys.path.insert(0, str(Path(row['path']).parent))
    import cut_sdf_fp32_control
    import cut_sdf_fp64
    if sha(root / 'gap.obj') != config['source_sha256']:
        raise ValueError('合法几何输入改变')
    checker = '/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646'
    if sha(checker) != '0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3':
        raise ValueError('完整检查器改变')
    check = json.loads(subprocess.run([checker, str(root / 'gap.obj')], check=True, capture_output=True, text=True).stdout)
    if not check['embedded_closed']:
        raise ValueError('场对照输入不合法')
    gap = trimesh.load(root / 'gap.obj', force='mesh', process=False)
    cube = trimesh.creation.box(extents=[.5, .5, .5])
    cube.vertices += .5
    out = root / 'result'
    out.mkdir(exist_ok=False)
    report = {'生成时间': datetime.now(timezone(timedelta(hours=8))).isoformat(), '修改时间及修改内容': '首次生成，三扩展两输入对照',
              '文档概述': 'FP64读取同一FP32可精确表达坐标，仅隔离计算差异，不运行完整PaMO',
              '索引目录': ['rows'], 'extensions': config['extensions'], 'source_sha256': config['source_sha256'],
              'source_embedding': check, 'full_PaMO_calls': 0, 'SDF_calls': 6, 'rows': []}
    for name, mesh, R in [('cube', cube, 64), ('gap', gap, 128)]:
        points = np.ascontiguousarray(mesh.vertices[mesh.faces], np.float32)
        if not np.array_equal(points.astype(np.float64), mesh.vertices[mesh.faces]):
            raise ValueError('控制源不是FP32可精确表达坐标')
        fields = {}
        row = {'input': name, 'R': R, 'band': 3 / 256 if name == 'gap' else 3 / R, 'fields': [], 'comparisons': []}
        for label, module, dtype in [('author', torchcumesh2sdf, np.float32), ('FP32_same_flags', cut_sdf_fp32_control, np.float32), ('FP64_same_flags', cut_sdf_fp64, np.float64)]:
            # FP64控制由同一FP32坐标精确提升，禁止混入归一化坐标变化。
            d = module.get_sdf(torch.from_numpy(points.astype(dtype)).cuda(), R, row['band'])
            torch.cuda.synchronize()
            a = d.cpu().numpy()
            fields[label] = a
            path = out / (name + '_' + label + '.npz')
            np.savez_compressed(path, sdf=a)
            info = {'label': label, 'sha256': sha(path), 'finite': bool(np.isfinite(a).all()), 'negative_cells': int((a < 0).sum())}
            if name == 'cube':
                xyz = (np.indices((R, R, R)).transpose(1, 2, 3, 0) + .5) / R
                q = np.abs(xyz - .5) - .25
                answer = np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(axis=-1), 0)
                near = np.abs(answer) < row['band']
                info.update(sign_mismatches=int(((a < 0) != (answer < 0)).sum()),
                            near_distance_max_error=float(np.max(np.abs(a[near] - answer[near]))))
            row['fields'].append(info)
        for left, right in [('author', 'FP32_same_flags'), ('FP32_same_flags', 'FP64_same_flags')]:
            a, b = fields[left], fields[right]
            row['comparisons'].append({'left': left, 'right': right, 'cells': int(a.size),
                                       'changed_cells': int((a != b).sum()), 'max_abs_delta': float(np.max(np.abs(a - b))),
                                       'sign_changed_cells': int(((a < 0) != (b < 0)).sum())})
        report['rows'].append(row)
    (out / '01-三扩展两合法输入GPU场核查.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
