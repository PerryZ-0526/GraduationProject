"""同一物理输出的实际CUDA及Warp表示核对，保留世界FP32反例。"""
from pathlib import Path
import json
import hashlib
import subprocess
from datetime import datetime, timezone, timedelta
import numpy as np
import trimesh
import torch
import warp as wp

folder = Path(__file__).parent
config = json.loads((folder / 'config.json').read_text('utf8'))
mesh = trimesh.load(folder / 'candidate.obj', process=False)
v, f = np.asarray(mesh.vertices), np.asarray(mesh.faces)
checker = Path('/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646')
assert hashlib.sha256(checker.read_bytes()).hexdigest() == '0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3'
wp.init()
record = {'生成时间': datetime.now(timezone(timedelta(hours=8))).isoformat(), '修改时间及修改内容': '首次生成同源实际表示核对',
          '文档概述': '只有张量编码和全量嵌入检查，不是完整原求解或连续发布', '索引目录': ['rows'], 'status': 'running', 'rows': []}
for name, origin in config['origins']:
    local = v - np.asarray(origin)
    cuda = torch.as_tensor(local, dtype=torch.float32, device='cuda').cpu().numpy()
    warp = wp.array(cuda.astype(np.float64) * config['scale'], dtype=wp.vec3, device='cuda:0').numpy()
    for kind, encoded, scale in [('CUDA', cuda, 1.), ('Warp', warp, config['scale'])]:
        path = folder / (name + '_' + kind + '.obj')
        with path.open('w', encoding='utf8') as stream:
            for p in encoded:
                stream.write('v ' + ' '.join(format(float(x), '.17g') for x in p) + '\n')
            for ids in f:
                stream.write('f ' + ' '.join(str(int(x)+1) for x in ids) + '\n')
        xyz = encoded.astype(np.float64) / scale
        t = xyz[f]
        area = .5 * np.linalg.norm(np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0]), axis=1)
        audit = json.loads(subprocess.run([str(checker), str(path)], capture_output=True, text=True, check=True).stdout)
        record['rows'].append({'origin_name': name, 'kind': kind, 'origin_mm': origin, 'scale': scale,
                              'encoded_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'embedding': audit,
                              'zero_area_faces': int((area == 0).sum()), 'small_faces_mm2': int((area <= 1e-12).sum()),
                              'minimum_area_mm2': float(area.min()), 'finite': bool(np.isfinite(encoded).all()),
                              'encoded_faces_unchanged': True})
        print(name, kind, 'zero', int((area == 0).sum()), 'small', int((area <= 1e-12).sum()), 'embedding', audit['embedded_closed'], flush=True)
record.update(status='completed', finished_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat())
(folder / '01-同源实际CUDA与Warp编码复核.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), 'utf8')
