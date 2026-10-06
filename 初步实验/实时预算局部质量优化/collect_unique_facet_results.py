"""核对完整CUDA反馈分母、父链、保存复审、质量统计及真实GPU像素。"""
from pathlib import Path
import datetime
import hashlib
import json
import numpy as np

ROOT = Path('/tmp/geogram_unique_facets_20261006_flat')
driver = ROOT/'03-唯一面扫描完整CUDA四预算反馈执行记录.json'
run = json.loads(driver.read_text(encoding='utf-8'))
assert run['status'] == 'completed' and len(run['trials']) == 6 and len(run['renders']) == 3


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stats(values):
    if not values:return None
    return {'samples': len(values), 'mean_ms': float(np.mean(values)), 'median_ms': float(np.median(values)),
            'p95_ms': float(np.percentile(values,95)), 'maximum_ms': float(np.max(values))}


for member, digest in run['frozen_workers'].items():
    assert sha(ROOT/'workers'/member) == digest
batches, records, objects = [], [], 0
for trial in run['trials']:
    out = Path(trial['output'])
    rp = out/'01-真实父反馈四预算完整记录.json'
    ap = out/'02-完整保存全量精确复审与四预算统计.json'
    assert trial['status'] == 'completed' and sha(rp) == trial['record_sha256'] and sha(ap) == trial['audit_sha256']
    record, audit = json.loads(rp.read_text()), json.loads(ap.read_text())
    assert record['status'] == audit['status'] == 'completed'
    assert audit['all_saved_published_and_sources_embedded'] and audit['all_parent_chains_valid']
    assert record['linear_unique_facets'] == trial['linear_unique_facets']
    assert len(record['routes']) == 4 and all(len(route['events']) == route['planned_events'] == 16 for route in record['routes'])
    records.append((trial,record))
    objects += audit['full_audited_objects']
    batches.append({'batch': out.name, 'objects': audit['full_audited_objects'], 'record_sha256': sha(rp), 'audit_sha256': sha(ap)})
groups = []
for enabled in (False,True):
    for budget in (20,50,100,200):
        events = [event for trial, record in records if trial['linear_unique_facets'] == enabled
                  for route in record['routes'] if route['budget_ms'] == budget for event in route['events']]
        assert len(events) == 48
        published = [event for event in events if event['status'] == 'published_verified']
        groups.append({'linear_unique_facets': enabled, 'budget_ms': budget, 'planned': len(events), 'published': len(published),
                       'within_budget': sum(not event['budget_overrun'] for event in published),
                       'rejected': sum(event['status'] == 'source_rejected' for event in events),
                       'blocked': sum(event['status'].startswith('blocked') for event in events),
                       'maintenance': stats([event['maintenance_total_ms'] for event in published]),
                       'whole': stats([event['cut_and_maintenance_ms'] for event in published]),
                       'boolean': stats([event['boolean']['boolean_ms'] for event in published]),
                       'quality_operations': sum(len((event.get('maintenance') or {}).get('operations',[])) for event in published),
                       'quality': {str(angle): {'count_gain': sum(event['source_quality'][str(angle)]['count']-event['output_quality'][str(angle)]['count'] for event in published),
                           'improved_frames': sum(event['source_quality'][str(angle)]['count']>event['output_quality'][str(angle)]['count'] for event in published),
                           'area_worse_frames': sum(event['source_quality'][str(angle)]['area_fraction']<event['output_quality'][str(angle)]['area_fraction'] for event in published)} for angle in (10,5,1)}})
renders = []
for row in run['renders']:
    path = Path(row['record'])
    assert sha(path) == row['sha256']
    data = json.loads(path.read_text())
    assert data['status'] == 'completed' and len(data['frames']) == len(data['audits'])
    assert all(audit['check']['embedded_closed'] for audit in data['audits'])
    assert 'NVIDIA' in data['renderer_capabilities']
    renders.append({'linear_unique_facets': row['linear_unique_facets'], 'budget_ms': row['budget_ms'],
                    'planned':16, 'rendered':len(data['frames']), 'pixels':stats([frame['tool_to_pixels_ms'] for frame in data['frames']]),
                    'render':stats([frame['publication_render_and_read_ms'] for frame in data['frames']]),
                    'record_sha256':sha(path), 'all_saved_arrays_embedded':True})
report = {'time_beijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
          'status':'completed', 'driver_sha256':sha(driver), 'planned_events':384, 'full_audited_objects':objects,
          'batches':batches, 'groups':groups, 'renders':renders, 'resource_isolation_not_proven':True,
          'scope':'固定四预算各自真实父链及保存对象完整复审；组件同源计时独立统计；GPU帧缓冲不代表客户端或屏幕呈现，也非长期稳定性证明'}
out = ROOT/'04-唯一面扫描四预算与真实GPU像素终态汇总.json'
assert not out.exists()
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({key:report[key] for key in ('status','planned_events','full_audited_objects','groups','renders')}),flush=True)
