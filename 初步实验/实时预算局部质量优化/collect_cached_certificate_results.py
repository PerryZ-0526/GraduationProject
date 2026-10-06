"""汇总完整缓存证书批次，保留旧校验失败、所有预算分母及实际像素记录。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    driver=root/'05-固定控制选择修正后完整GPU反馈执行记录.json';run=json.loads(driver.read_text())
    assert run['status']=='completed' and len(run['trials'])==6 and len(run['renders'])==3
    for path,expected in run['frozen_sources_and_libraries'].items():assert sha(root/path)==expected
    assert sha(root/'01-缓存源认证完整GPU反馈执行记录.json')==run['failed_record_sha256']
    component=json.loads((root/'02-缓存精确源证书九十六配对完整核对.json').read_text());assert component['pairs']==96
    controls=json.loads((root/'03-缓存证书完整正负控制.json').read_text());assert controls['all_decisions_identical']
    flips=json.loads((root/'04-缓存固定翻边协议及全量核对.json').read_text());assert flips['paired_runs']==48 and flips['protocol_controls']==6
    def stats(values):
        return dict(samples=len(values),mean_ms=float(np.mean(values)),median_ms=float(np.median(values)),
            p95_ms=float(np.percentile(values,95)),maximum_ms=float(np.max(values))) if values else None
    batches=[];all_records=[];total_objects=0
    for trial in run['trials']:
        out=root/f'r{trial["repeat"]}_{trial["variant"]}';rp=out/'01-真实父反馈四预算完整记录.json'
        ap=out/'02-完整保存全量精确复审与四预算统计.json'
        assert trial['status']=='completed' and sha(rp)==trial['record_sha256'] and sha(ap)==trial['audit_sha256']
        r,a=json.loads(rp.read_text()),json.loads(ap.read_text())
        assert r['status']==a['status']=='completed' and a['all_saved_published_and_sources_embedded'] and a['all_parent_chains_valid']
        assert len(r['routes'])==4 and all(len(route['events'])==route['planned_events']==16 for route in r['routes'])
        total_objects+=a['full_audited_objects'];all_records.append((trial,r))
        batches.append(dict(batch=out.name,objects=a['full_audited_objects'],record_sha256=sha(rp),audit_sha256=sha(ap)))
    groups=[]
    for variant in ['reference_workers','workers']:
        for budget in [20,50,100,200]:
            events=[e for t,r in all_records if t['variant']==variant for route in r['routes'] if route['budget_ms']==budget for e in route['events']]
            valid=[e for e in events if e['status']=='published_verified']
            groups.append(dict(variant=variant,budget_ms=budget,planned=len(events),published=len(valid),
                within_budget=sum(not e['budget_overrun'] for e in valid),rejected=sum(e['status']=='source_rejected' for e in events),
                blocked=sum(e['status'].startswith('blocked') for e in events),
                maintenance=stats([e['maintenance_total_ms'] for e in valid]),whole=stats([e['cut_and_maintenance_ms'] for e in valid]),
                source_certificate=stats([e['source_check']['total_elapsed_ms'] for e in valid]),
                quality_operations=sum(len((e.get('maintenance') or {}).get('operations',[])) for e in valid if e.get('final_check') and e['final_check']['embedded_closed']),
                quality={str(t):dict(count_gain=sum(e['source_quality'][str(t)]['count']-e['output_quality'][str(t)]['count'] for e in valid),
                    improved_frames=sum(e['source_quality'][str(t)]['count']>e['output_quality'][str(t)]['count'] for e in valid),
                    area_worse_frames=sum(e['source_quality'][str(t)]['area_fraction']<e['output_quality'][str(t)]['area_fraction'] for e in valid),
                    area_gain=sum(e['source_quality'][str(t)]['area_fraction']-e['output_quality'][str(t)]['area_fraction'] for e in valid)) for t in [10,5,1]}))
    renders=[]
    for row in run['renders']:
        path=Path(row['path']);assert sha(path)==row['sha256'];data=json.loads(path.read_text())
        assert data['status']=='completed' and len(data['frames'])==len(data['audits'])
        assert all(a['check']['embedded_closed'] for a in data['audits']) and 'NVIDIA' in data['renderer_capabilities']
        feedback=json.loads((path.parent/'feedback/01-真实父反馈四预算完整记录.json').read_text())
        arrivals={e['step']:e['tool_arrival_perf_counter'] for route in feedback['routes'] for e in route['events'] if 'tool_arrival_perf_counter' in e}
        ends=[arrivals[f['step']]+f['tool_to_pixels_ms']/1000 for f in data['frames']]
        renders.append(dict(variant=row['variant'],budget_ms=row['budget'],planned=16,rendered=len(data['frames']),
            pixels=stats([f['tool_to_pixels_ms'] for f in data['frames']]),render=stats([f['publication_render_and_read_ms'] for f in data['frames']]),
            pixel_intervals_with_offline_work=stats([1000*(b-a) for a,b in zip(ends,ends[1:])]),
            record_sha256=sha(path),all_saved_arrays_embedded=True,renderer_capabilities=data['renderer_capabilities']))
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',planned_events=384,
        driver_sha256=sha(driver),old_failure_sha256=run['failed_record_sha256'],component_pairs=96,
        component={name:stats([r[name]['total_elapsed_ms'] for r in component['rows']]) for name in ['reference','cached']},
        certificate_controls=controls['controls'],fixed_flip_pairs=48,fixed_flip_controls=6,
        batches=batches,full_audited_objects=total_objects,groups=groups,renders=renders,resource_isolation_not_proven=True,
        scope='同源精确证书逐项配对与完整GPU实际链；各预算沿自身父网格，像素不是屏幕扫描呈现；无任意输入实时保证')
    path=root/'06-缓存源认证三轮四预算与真实像素终态汇总.json';assert not path.exists()
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['batches','renders']}))


if __name__=='__main__':main()
