"""完整分母汇总本机长反馈、真实队列和同次源质量，不跨硬件作加速结论。"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import numpy as np


ROOT = Path('D:/GraduationProject实验输出/20261007_自适应方向认证本机完整长轨迹')


def read(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))


def stats(values):
    a = np.asarray(values, dtype=float)
    return dict(count=len(a), mean_ms=float(a.mean()), median_ms=float(np.median(a)),
                p95_ms=float(np.percentile(a, 95)), max_ms=float(a.max()))


def main():
    execution = read('02-常驻长序列完整记录.json')
    audit = read('04-保存对象完整精确复审.json')
    geometry = read('05-独立材料参照逐帧有限探针.json')
    live = read('live_queue/01-真实输入队列与GPU像素完整记录.json')
    assert execution['status'] == 'completed_with_recorded_failures' and len(execution['runs']) == 4
    assert audit['status'] == geometry['status'] == 'completed' and not audit['failed_published_checks']
    assert len(audit['audits']) == 1536 and all(sum(run['statuses'].values()) == 384 for run in execution['runs'])
    # 重读实际源和输出的顶点字节，不能用宽松数值相等代替不移动证明。
    fixed = 0
    quality = {}
    for run in execution['runs']:
        if run['reference']:
            continue
        folder = Path(run['output'])
        selected = [row for row in audit['audits'] if row['route'] == run['route'] and not row['reference'] and row['status'] == 'published_verified']
        for row in selected:
            with np.load(folder/f'e{row["step"]:03d}_source.npz') as source, np.load(folder/f'e{row["step"]:03d}_output.npz') as output:
                assert source['vertices'].tobytes() == output['vertices'].tobytes()
                fixed += 1
        quality[run['route']] = dict(published=len(selected), thresholds={angle:{
            'count_improved':sum(x['output_quality'][angle]['count'] < x['source_quality'][angle]['count'] for x in selected),
            'count_worse':sum(x['output_quality'][angle]['count'] > x['source_quality'][angle]['count'] for x in selected),
            'area_improved':sum(x['output_quality'][angle]['area_fraction'] < x['source_quality'][angle]['area_fraction'] for x in selected),
            'area_worse':sum(x['output_quality'][angle]['area_fraction'] > x['source_quality'][angle]['area_fraction'] for x in selected),
            'bad_face_count_reduction_sum':sum(x['source_quality'][angle]['count']-x['output_quality'][angle]['count'] for x in selected)
        } for angle in ('10', '5', '1')})
    assert fixed == 157
    queue = []
    for run in live['runs']:
        assert run['planned_events'] == 384
        assert run['arrived']+run['schedule_cancelled'] == 384
        assert len(run['frames']) == len(run['full_saved_audits']) == run['published']
        assert all(x['check']['embedded_closed'] for x in run['full_saved_audits'])
        queue.append(dict(hz=run['hz'], planned=384, published=run['published'], arrived=run['arrived'],
                          queued_at_stop=run['queued_at_stop'], schedule_cancelled=run['schedule_cancelled'],
                          first_rejection=run['first_rejection'], input_to_pixels=stats([x['input_to_pixels_ms'] for x in run['frames']]),
                          waiting=stats([x['waiting_ms'] for x in run['frames']]),
                          service_to_pixels=stats([x['active_service_to_pixels_ms'] for x in run['frames']])))
    result = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(), status='completed_with_recorded_failures',
                  planned_feedback_events=1536, candidate_planned=768, candidate_published=157,
                  saved_objects=sum(len(x['checks']) for x in audit['audits']), valid_published_outputs=314,
                  valid_published_sources=314, vertex_bytes_fixed=fixed, parent_chains_verified=audit['parent_chains_checked'],
                  quality=quality, actual_queue=queue, geometry_comparisons=len(geometry['comparisons']),
                  finite_probe_max_mm=max(x['probe_max_mm'] for x in geometry['comparisons']),
                  reference='共享切削与必要修复的独立无可选质量材料链，非独立算法真值',
                  hardware='本机CPU维护和Intel Arc离屏渲染；不与远端不同版本、父网格和设备直接相除',
                  conclusion='合法前缀速度已接近交互要求，但完整路线仍因源自交拒绝，未实现连续实时建模',
                  evidence_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                      '00-完整长轨迹输入与本机方法冻结.json', '02-常驻长序列完整记录.json',
                      '04-保存对象完整精确复审.json', '05-独立材料参照逐帧有限探针.json',
                      'live_queue/01-真实输入队列与GPU像素完整记录.json')})
    target = ROOT/'07-完整长反馈与实际队列联合汇总.json'
    assert not target.exists()
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
