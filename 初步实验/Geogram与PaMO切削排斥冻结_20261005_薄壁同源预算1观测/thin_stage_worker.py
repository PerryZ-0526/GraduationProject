"""窄缝第二刀固定同源FP64归一化的完整三阶段开发，不直接发布。"""

import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
import textwrap
from time import perf_counter
from datetime import datetime, timezone, timedelta
import numpy as np
import torch
import trimesh


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    cfg = json.loads((root / 'inputs.json').read_text('utf8'))
    old = Path(cfg['old_diagnostic_root'])
    original = json.loads((old / 'inputs.json').read_text('utf8'))
    # 静态修复对照可显式绑定新物理源，禁止无摘要替换旧输入。
    source_binding = cfg.get('source_override', original['source'])
    source_path = (root if 'source_override' in cfg else old) / source_binding['file']
    if sha(source_path) != source_binding['sha256']:
        raise ValueError('固定物理输入改变')
    ext = original['sorted_extension']
    if sha(ext['extension']) != ext['extension_sha256']:
        raise ValueError('排序扩展改变')
    spec = importlib.util.spec_from_file_location(ext['module'], ext['extension'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules['pamo._C'] = module
    import pamo
    if sha(inspect.getfile(pamo.PaMO)) != '0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a':
        raise ValueError('作者完整阶段改变')
    if sha(pamo.torchcumesh2sdf.__file__) != 'c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad':
        raise ValueError('作者SDF改变')
    if sha(cfg['SDF_extension']) != cfg['SDF_extension_sha256']:
        raise ValueError('FP64候选二进制改变')
    sys.path.insert(0, str(Path(cfg['SDF_extension']).parent))
    import cut_sdf_fp64
    pamo.torchcumesh2sdf = cut_sdf_fp64
    from pamo_safe_project import Stage3Config
    if sha(inspect.getfile(Stage3Config)) != 'df1eb24db57394c32e31f6d67a58cd7ef6c25febc11aff39c5e9503ee82d6390':
        raise ValueError('阶段三配置改变')
    init = Stage3Config.__init__

    def larger(self, *args, **kwargs):
        # 与前版开发保持相同隔离容量，避免改作者安装配置。
        init(self, *args, **kwargs)
        assert self.max_blocks == 1 << 25
        self.max_blocks = 1 << 26

    Stage3Config.__init__ = larger
    out = root / 'result'
    out.mkdir(exist_ok=False)
    original_preprocess = pamo.PaMO.preprocess_mesh

    def preprocess(self, points, faces, band, margin):
        _, minimum, maximum, mean = original_preprocess(self, points, faces, band, margin)
        centered = points - torch.from_numpy(mean).to(points.device)
        t = centered[faces.long()]
        area = torch.linalg.vector_norm(torch.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0], dim=1), dim=1)
        if bool(((area == 0) | ~torch.isfinite(area)).any()):
            raise RuntimeError('实际碰撞源退化，禁止完整求解')
        # 保留原均值、范围、碰撞源；仅SDF归一化三角数组不再转回FP32。
        n = np.asarray(points.cpu().numpy(), np.float64)[faces.cpu().numpy()]
        n = ((n - np.asarray(mean, np.float64) - np.asarray(minimum, np.float64)) / float(maximum) + float(band)) / float(margin)
        return np.ascontiguousarray(n, np.float64), minimum, maximum, mean

    pamo.PaMO.preprocess_mesh = preprocess
    from normalized_working_source_gate import install_working_source_gate
    install_working_source_gate(out / 'working_sources')
    from sdf_bias_remesh import install_bias
    install_bias(0.)
    if cfg.get('minimum_sdf_resolution') is not None:
        if cfg['minimum_sdf_resolution'] != 256:
            raise ValueError('本次最低分辨率候选只允许固定256')
        original_remesh = pamo.PaMO.remesh

        def remesh(self, *args, **kwargs):
            # 所有输入统一提高最低分辨率，不按当前形状写专用偏移或更改band。
            self.R = max(self.R, cfg['minimum_sdf_resolution'])
            return original_remesh(self, *args, **kwargs)

        pamo.PaMO.remesh = remesh
    run_source = textwrap.dedent(inspect.getsource(pamo.PaMO.run))
    old_tensor = "tris = torch.tensor(tris, dtype=torch.float32, device='cuda:0')"
    if run_source.count(old_tensor) != 1:
        raise ValueError('作者归一化张量入口结构变化')
    # 只替换隔离函数中的SDF张量精度，原简化、投影及目标面数代码不改。
    changed_run = run_source.replace(old_tensor, "# 归一化SDF三角数组以FP64送入独立扩展。\n    tris = torch.tensor(tris, dtype=torch.float64, device='cuda:0')")
    namespace = dict(pamo.PaMO.run.__globals__)
    exec(compile(changed_run, str(root / 'isolated_run_fp64.py'), 'exec'), namespace)
    pamo.PaMO.run = namespace['run']
    (out / 'isolated_run_fp64.py').write_text(changed_run, 'utf8')
    source = trimesh.load(source_path, force='mesh', process=False)
    # 显式固定修复前原点，以区分局部修复与新均值原点的表示影响。
    origin = np.asarray(cfg.get('origin_override_mm', original['origin_mm']), np.float64)
    local = source.copy()
    local.vertices = np.asarray(source.vertices, np.float64) - origin
    points = torch.from_numpy(np.asarray(local.vertices, np.float32)).cuda()
    faces = torch.from_numpy(np.asarray(local.faces, np.int32)).cuda()
    model = pamo.PaMO(local, use_stage1=True, use_stage3=True)
    torch.cuda.synchronize()
    start = perf_counter()
    from thin_full_stage_observation import install_stage_observation
    install_stage_observation(out / 'stage_observations', origin)
    v, f = model.run(points, faces, ratio=1., min_verts=0)
    torch.cuda.synchronize()
    mesh = trimesh.Trimesh(np.asarray(v, np.float64) + origin, f, process=False)
    path = out / 'raw_full_candidate.obj'
    with path.open('w', encoding='utf8') as stream:
        for point in mesh.vertices:
            stream.write('v ' + ' '.join(format(float(x), '.17g') for x in point) + '\n')
        for face in mesh.faces:
            stream.write('f ' + ' '.join(str(int(x) + 1) for x in face) + '\n')
    checker = '/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646'
    if sha(checker) != '0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3':
        raise ValueError('完整输出检查器改变')
    check = json.loads(subprocess.run([checker, str(path)], check=True, capture_output=True, text=True).stdout)
    record = {'生成时间': datetime.now(timezone(timedelta(hours=8))).isoformat(),
              '修改时间及修改内容': '首次生成，固定第二刀完整三阶段',
              '文档概述': '原始PaMO输出，不是维护发布，无后续父反馈', '索引目录': ['source_sha256', 'output'],
              'source_sha256': sha(source_path), 'SDF_extension_sha256': cfg['SDF_extension_sha256'],
              'origin_mm': origin.tolist(),
              'actual_sdf_resolution': model.R,
              'isolated_run_sha256': sha(out / 'isolated_run_fp64.py'),
              'full_PaMO_calls': 1, 'new_publications': 0, 'full_ms': (perf_counter() - start) * 1000,
              'finite': bool(np.isfinite(mesh.vertices).all()), 'zero_or_small_faces': int((mesh.area_faces <= 1e-12).sum()),
              'components': len(mesh.split(only_watertight=False)), 'source_components': len(source.split(only_watertight=False)),
              'euler': int(mesh.euler_number), 'source_euler': int(source.euler_number),
              'output': path.name, 'output_sha256': sha(path), 'embedding': check}
    (out / '01-薄壁首刀完整三阶段观测终态.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
