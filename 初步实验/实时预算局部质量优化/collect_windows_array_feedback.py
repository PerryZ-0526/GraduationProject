"""核对本机完整分母、父链及实际显示数组，分别统计CPU维护与Arc帧缓冲时延。"""
from pathlib import Path
import datetime
import hashlib
import json
import numpy as np

ROOT=Path('D:/GraduationProject实验输出/20261007_数组源证书本机完整反馈')
driver=ROOT/'09-Windows扫描库身份修订完整链路执行记录.json'
run=json.loads(driver.read_text(encoding='utf-8'))
assert run['status']=='completed' and len(run['trials'])==6 and len(run['renders'])==3
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for member,digest in run['frozen_files'].items():assert sha(ROOT/member)==digest


def stats(values):
    if not values:return None
    return dict(samples=len(values),mean_ms=float(np.mean(values)),median_ms=float(np.median(values)),
                p95_ms=float(np.percentile(values,95)),maximum_ms=float(np.max(values)))


records=[];objects=0;batches=[]
for trial in run['trials']:
    out=Path(trial['output']);rp=out/'01-真实父反馈四预算完整记录.json';ap=out/'02-完整保存全量精确复审与四预算统计.json'
    assert trial['status']=='completed' and sha(rp)==trial['record_sha256'] and sha(ap)==trial['audit_sha256']
    r,a=json.loads(rp.read_text(encoding='utf-8')),json.loads(ap.read_text(encoding='utf-8'))
    assert r['status']==a['status']=='completed' and r['edge_backend']=='cpu'
    assert r['certified_operand_pairs'] and r['linear_unique_facets'] and r['no_full_pamo']
    assert a['all_saved_published_and_sources_embedded'] and a['all_parent_chains_valid']
    assert len(r['routes'])==4 and all(len(route['events'])==route['planned_events']==16 for route in r['routes'])
    objects+=a['full_audited_objects'];records.append((trial,r))
    batches.append(dict(name=out.name,objects=a['full_audited_objects'],record_sha256=sha(rp),audit_sha256=sha(ap)))
groups=[]
for variant in ['reference_workers','workers']:
    for budget in [20,50,100,200]:
        events=[e for t,r in records if t['variant']==variant for route in r['routes'] if route['budget_ms']==budget for e in route['events']]
        assert len(events)==48
        pub=[e for e in events if e['status']=='published_verified']
        groups.append(dict(variant=variant,budget_ms=budget,planned=len(events),published=len(pub),
            within_budget=sum(not e['budget_overrun'] for e in pub),rejected=sum(e['status']=='source_rejected' for e in events),
            blocked=sum(e['status'].startswith('blocked') for e in events),
            maintenance=stats([e['maintenance_total_ms'] for e in pub]),whole=stats([e['cut_and_maintenance_ms'] for e in pub]),
            boolean=stats([e['boolean']['boolean_ms'] for e in pub]),source_certificate=stats([e['source_check']['total_elapsed_ms'] for e in pub]),
            quality_operations=sum(len((e.get('maintenance') or {}).get('operations',[])) for e in pub),
            quality={str(angle):dict(count_gain=sum(e['source_quality'][str(angle)]['count']-e['output_quality'][str(angle)]['count'] for e in pub),
                improved_frames=sum(e['source_quality'][str(angle)]['count']>e['output_quality'][str(angle)]['count'] for e in pub),
                area_worse_frames=sum(e['source_quality'][str(angle)]['area_fraction']<e['output_quality'][str(angle)]['area_fraction'] for e in pub),
                area_fraction_gain=sum(e['source_quality'][str(angle)]['area_fraction']-e['output_quality'][str(angle)]['area_fraction'] for e in pub)) for angle in [10,5,1]}))
renders=[]
for row in run['renders']:
    path=Path(row['path']);assert sha(path)==row['sha256'];d=json.loads(path.read_text(encoding='utf-8'))
    assert d['status']=='completed' and d['maintenance_backend']=='cpu' and d['platform']=='Windows'
    assert len(d['frames'])==len(d['audits'])==16
    assert 'Intel(R) Arc(TM) 130T' in d['renderer_capabilities']
    assert all(a['check']['embedded_closed'] and sha(a['path'])==a['sha256'] for a in d['audits'])
    renders.append(dict(variant=row['variant'],budget=row['budget'],rendered=16,
        pixels=stats([f['tool_to_pixels_ms'] for f in d['frames']]),render=stats([f['publication_render_and_read_ms'] for f in d['frames']]),
        record_sha256=sha(path),all_display_arrays_embedded=True,renderer='Intel Arc 130T',cold_first_render_included=True))
component=json.loads((ROOT/'02-缓存精确源证书九十六配对完整核对.json').read_text(encoding='utf-8'))
assert component['pairs']==96 and component['all_decisions_counters_and_parent_transitions_identical']
topology=json.loads((ROOT/'07-数组拓扑排序多环与非法输入控制.json').read_text(encoding='utf-8'))
near=json.loads((ROOT/'05-过滤谓词五十近接触尺度控制.json').read_text(encoding='utf-8'))
flips=json.loads((ROOT/'08-本机原翻边协议与完整检查.json').read_text(encoding='utf-8'))
assert topology['controls']==58 and topology['error_controls']==3 and near['controls']==50
assert flips['paired_runs']==48 and flips['protocol_controls']==6
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='completed',
    driver_sha256=sha(driver),planned_feedback_events=384,full_audited_objects=objects,batches=batches,groups=groups,renders=renders,
    component_pairs=96,topology_controls=58,illegal_array_controls=3,near_contact_controls=50,fixed_flip_pairs=48,negative_flip_controls=6,
    component={key:stats([r[key]['total_elapsed_ms'] for r in component['rows']]) for key in ['reference','cached']},
    resource_isolation_not_proven=True,scope='本机CPU建模维护和Arc真实帧缓冲，已见CT输入各自父链；不含正常磁盘证据保存及全量离线统计、客户端传输、实际队列或屏幕呈现，非远端CUDA结论')
target=ROOT/'10-本机完整四预算与Arc像素终态汇总.json';assert not target.exists()
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='completed',planned=384,objects=objects,groups=groups,renders=renders)),flush=True)
