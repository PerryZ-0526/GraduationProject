"""原求解前的同源低面积面控制；实际编码误差限定局部折叠。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import hashlib
import subprocess
import numpy as np
from encoding_bound_small_face_endpoint import endpoint_collapse

def install_area_control(encoding_error_mm, output):
    import pamo_safe_project as package
    from pamo_safe_project import processing
    original = package.process
    output = Path(output)
    output.mkdir(exist_ok=False)
    checker = Path('/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646')
    assert hashlib.sha256(checker.read_bytes()).hexdigest() == '0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3'
    def process(gt_V, gt_F, stage2_V, stage2_F, n_iters, system=None, config=None, eval=False, return_curve=False):
        author_scale, _ = processing.get_normalization_transform(gt_V)
        scale = float(2. ** np.floor(np.log2(author_scale)))
        v, f = np.asarray(stage2_V), np.asarray(stage2_F)
        q = np.asarray(v * scale, np.float32)
        def small(q, f):
            p = q.astype(np.float64) / scale
            triangles = p[f]
            areas = .5 * np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0], triangles[:,2]-triangles[:,0]), axis=1)
            return np.flatnonzero(areas <= 1e-12)
        initial = len(small(q, f))
        budget = 2 * float(encoding_error_mm)
        now = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
        record = {'生成时间': now, '修改时间及修改内容': now + '；首次生成编码预算面积控制',
                  '文档概述': '不改碰撞源和最终面积门槛；中间低面积面数必须严格下降',
                  '索引目录': ['parameters', 'collapses'], 'initial_small_faces': initial,
                  'source_encoding_error_mm': encoding_error_mm, 'per_edge_and_plane_budget_mm': budget,
                  'budget_origin': 'two_endpoint_initial_source_encoding_error_sum',
                  'physical_area_floor_mm2': 1e-12, 'collapses': [], 'status': 'checking'}
        path = output / '01-实际编码误差预算低面积处理.json'
        def save():
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2), 'utf8')
        save()
        total_bound = 0.
        for step in range(initial):
            bad = small(q, f)
            if not len(bad):
                break
            physical = q.astype(np.float64) / scale
            edges = {tuple(sorted([int(a), int(b)])) for face in f[bad] for a, b in zip(face, np.roll(face, -1))}
            accepted = False
            for edge in sorted(edges, key=lambda e: (float(np.linalg.norm(physical[e[0]]-physical[e[1]])), e)):
                length = float(np.linalg.norm(physical[edge[0]]-physical[edge[1]]))
                if length > budget:
                    continue
                proposal, detail = endpoint_collapse(v, f, edge, q, scale, budget)
                if proposal is None:
                    record.setdefault('rejected_proposals', []).append(detail)
                    continue
                vv, ff, qq = proposal
                obj = output / ('proposal_' + str(step) + '.obj')
                with obj.open('w', encoding='utf8') as stream:
                    for point in qq:
                        stream.write('v ' + ' '.join(format(float(x), '.17g') for x in point) + '\n')
                    for face in ff:
                        stream.write('f ' + ' '.join(str(int(x)+1) for x in face) + '\n')
                run = subprocess.run([str(checker), str(obj)], capture_output=True, text=True, check=True)
                embedding = json.loads(run.stdout)
                if not embedding['embedded_closed']:
                    record.setdefault('rejected_proposals', []).append({'embedding': embedding, 'edge': list(edge)})
                    continue
                assert np.array_equal(qq, np.asarray(vv * scale, np.float32))
                remaining = len(small(qq, ff))
                assert remaining < len(bad)
                detail.pop('remaining_original_vertex_ids')
                detail.update(actual_encoded_embedding=embedding, remaining_small_faces=remaining,
                              collapse_correspondence_upper_bound_mm=length,
                              retained_vertex_encoding_bitwise_unchanged=True)
                record['collapses'].append(detail)
                total_bound += length
                v, f, q = vv, ff, qq
                accepted = True
                save()
                break
            if not accepted:
                record.update(status='rejected', reason='no_exact_embedded_endpoint_in_actual_encoding_budget')
                save()
                raise RuntimeError(record['reason'])
        assert not len(small(q, f))
        record.update(status='completed_area_conditioning', final_small_faces=0,
                      final_faces=len(f), conservative_summed_collapse_correspondence_bound_mm=total_bound,
                      bound_scope='仅相对本次候选的局部边折叠同连接映射，不是对累计目标的距离证书')
        save()
        # 原二次幂表示、完整原能量、接触处理和CCD继续执行，碰撞源参数原样传递。
        return original(gt_V, gt_F, v, f, n_iters, system, config, eval, return_curve)
    package.process = process
    processing.process = process
