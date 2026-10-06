"""在尺度变化与一ULP近接触输入上核对过滤谓词、原证书和全量EPECK。"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
import trimesh
from incremental_mesh_memory import VerifiedMesh
from exact_mesh_memory import ExactMeshMemory


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    root = args.root.resolve()
    path = root / 'reference_workers/incremental_mesh_memory.py'
    spec = importlib.util.spec_from_file_location('filtered_controls_reference', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    full = ExactMeshMemory()
    mesh = trimesh.creation.box(extents=[2, 2, 2])
    v, f = np.asarray(mesh.vertices), np.asarray(mesh.faces)
    keys = ['topology_valid', 'closed', 'embedded_closed', 'self_intersection_pairs', 'exact_degenerate_faces']
    rows = []
    for exponent in [-200, -40, 0, 40, 200]:
        scale = np.ldexp(1., exponent)
        for rotation in ['轴对齐', '准确斜置']:
            # 斜置矩阵的分量均为二进制准确数，不使用近似旋转的理想几何作真值。
            matrix = np.eye(3) if rotation == '轴对齐' else np.array([[1., .5, 0.], [0., 1., .5], [.5, 0., 1.]])
            initial = np.vstack((v, v + [4., 0., 0.])) @ matrix.T * scale
            faces = np.vstack((f, f + len(v)))
            old, new = module.VerifiedMesh(), VerifiedMesh()
            assert old.check(initial, faces, True)['embedded_closed']
            assert new.check(initial, faces, True)['embedded_closed']
            for name, shift in [('一ULP间隔', np.nextafter(2., np.inf)), ('面接触', 2.),
                                ('一ULP穿入', np.nextafter(2., 0.)), ('边接触', 2.), ('完全重合', 0.)]:
                offset = [shift, 2. if name == '边接触' else 0., 0.]
                actual = np.vstack((v, v + offset)) @ matrix.T * scale
                a, b, c = old.check(actual, faces), new.check(actual, faces), full.audit(actual, faces)
                assert all(a[k] == b[k] == c[k] for k in keys), (exponent, rotation, name, a, b, c)
                # 任何未采用输入都不得改动原父证书，尤其接触和交叠负例。
                before = new.handle
                identity = new.check(initial, faces)
                assert identity['embedded_closed'] and new.handle == before
                rows.append(dict(exponent=exponent, rotation=rotation, case=name,
                    vertices_sha256=hashlib.sha256(actual.tobytes()).hexdigest(),
                    reference=a, filtered=b, full=c, parent_preserved=True))
            old.close()
            new.close()
    assert len(rows) == 50
    report = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(), status='completed',
        controls=len(rows), all_decisions_identical=True, rows=rows,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='五尺度两种准确坐标构型及五种实际浮点接触，验证保存坐标几何，不称任意输入保证')
    target = root / '05-过滤谓词五十近接触尺度控制.json'
    assert not target.exists()
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(dict(controls=50, all_decisions_identical=True)))


if __name__ == '__main__':
    main()
