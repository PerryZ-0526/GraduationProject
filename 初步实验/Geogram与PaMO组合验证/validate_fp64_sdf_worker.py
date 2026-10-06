"""隔离FP64符号场的解析立方体及窄缝第二刀第一阶段核查。"""

import hashlib
import argparse
import importlib.util
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gap-only', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    binding = json.loads((root / "02-隔离扩展构建终态.json").read_text("utf8"))
    if sha(binding["extension"]) != binding["extension_sha256"]:
        raise ValueError("候选二进制改变")
    sys.path.insert(0, str(Path(binding["extension"]).parent))
    import cut_sdf_fp64
    import torchcumesh2sdf
    original_sha = sha(torchcumesh2sdf.__file__)
    if original_sha != "c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad":
        raise ValueError("作者扩展改变")
    out = root / ("validation_inverse_fp32" if args.gap_only else "validation")
    out.mkdir(exist_ok=False)
    report = {"生成时间": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "修改时间及修改内容": "首次生成，解析控制及保存场第一阶段",
              "文档概述": "没有完整PaMO或发布；作者与候选编译配置不同，不单独归因精度",
              "索引目录": ["cube", "gap"], "candidate_sha256": binding["extension_sha256"],
              "original_sha256": original_sha, "full_PaMO_calls": 0, "cube": []}
    cube = trimesh.creation.box(extents=[.5, .5, .5])
    cube.vertices += .5
    triangles = np.ascontiguousarray(cube.vertices[cube.faces], np.float64)
    R = 64
    xyz = (np.indices((R, R, R)).transpose(1, 2, 3, 0) + .5) / R
    q = np.abs(xyz - .5) - .25
    answer = np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(np.max(q, axis=-1), 0)
    # 排除恰好边界点，距离仅在原栅格窄带有候选保证的区域比较。
    sign_mask = np.abs(answer) > 1e-12
    near = np.abs(answer) < 3 / R
    variants = [] if args.gap_only else [("author_FP32", torchcumesh2sdf, np.float32), ("candidate_FP64", cut_sdf_fp64, np.float64)]
    for label, module, dtype in variants:
        d = module.get_sdf(torch.from_numpy(triangles.astype(dtype)).cuda(), R, 3 / R)
        torch.cuda.synchronize()
        a = d.cpu().numpy()
        np.savez_compressed(out / (label + ".npz"), sdf=a)
        report["cube"].append({"variant": label, "finite": bool(np.isfinite(a).all()),
                               "sign_queries": int(sign_mask.sum()),
                               "sign_mismatches": int(((a < 0) != (answer < 0))[sign_mask].sum()),
                               "near_queries": int(near.sum()),
                               "near_distance_max_error": float(np.max(np.abs(a[near] - answer[near]))),
                               "field_sha256": sha(out / (label + ".npz"))})
    old = Path('/root/autodl-tmp/graduation_project/constrained_20261005_窄缝第二刀四归一化表示GPU预处理诊断_f21bf357d960')
    cfg = json.loads((old / "inputs.json").read_text("utf8"))
    ext = cfg["sorted_extension"]
    if sha(ext["extension"]) != ext["extension_sha256"]:
        raise ValueError("简化扩展改变")
    spec = importlib.util.spec_from_file_location(ext["module"], ext["extension"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules['pamo._C'] = module
    import pamo
    import inspect
    if sha(inspect.getfile(pamo.PaMO)) != '0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a':
        raise ValueError("作者PaMO改变")
    params = json.loads((old / 'result/07-第二刀四归一化表示实际预处理诊断.json').read_text('utf8'))['parameters']
    field_record = json.loads((root / '03-首个双精度输入场终态.json').read_text('utf8'))
    if sha(field_record['field']) != field_record['field_sha256']:
        raise ValueError("实际保存场改变")
    with np.load(field_record['field']) as z:
        field = torch.from_numpy(z['sdf']).cuda()
    source = trimesh.load(old / 'result/04-初始CUDA源全FP64归一化几何控制.obj', force='mesh', process=False)
    if sha(old / 'result/04-初始CUDA源全FP64归一化几何控制.obj') != field_record['source_sha256']:
        raise ValueError("场源改变")
    model = pamo.PaMO(source, use_stage1=True, use_stage3=False)
    vertices, faces = model.vol2mesh(field, return_quads=False)
    # 作者minimum原数组为FP32，JSON恢复时显式保持其精度，再FP64加世界原点。
    v = vertices.cpu().numpy()
    v = (((v * 256 + .5) / 257 * params['margin'] - params['band']) * params['maximum_span_mm'] + np.asarray(params['minimum_mm'], np.float32))
    v = np.asarray(v, np.float32) + np.asarray(params['mean_mm'], np.float32)
    mesh = trimesh.Trimesh(np.asarray(v, np.float64) + params['origin_mm'], faces.cpu().numpy(), process=False)
    path = out / '零偏移第二刀第一阶段.obj'
    with path.open('w', encoding='utf8') as f:
        for point in mesh.vertices:
            f.write('v ' + ' '.join(format(float(x), '.17g') for x in point) + '\n')
        for face in mesh.faces:
            f.write('f ' + ' '.join(str(int(x) + 1) for x in face) + '\n')
    checker = '/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646'
    if sha(checker) != '0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3':
        raise ValueError("完整检查器改变")
    check = json.loads(subprocess.run([checker, str(path)], check=True, capture_output=True, text=True).stdout)
    report['gap'] = {'source_sha256': field_record['source_sha256'], 'field_sha256': field_record['field_sha256'],
                     'output_sha256': sha(path), 'components': len(mesh.split(only_watertight=False)),
                     'source_components': len(source.split(only_watertight=False)), 'euler': int(mesh.euler_number),
                     'source_euler': int(source.euler_number), 'vertices': len(mesh.vertices), 'faces': len(mesh.faces), 'embedding': check}
    (out / '01-解析控制与窄缝第一阶段核查.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
