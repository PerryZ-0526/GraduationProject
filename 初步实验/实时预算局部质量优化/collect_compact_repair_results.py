"""从完整终态记录汇总短边修复与真实GPU渲染，不丢弃拒绝和受阻分母。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--render-name',default='render_trials');args=p.parse_args()
    root=args.root.resolve();sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    driver=root/'01-紧凑短边修复完整GPU批次执行记录.json';run=json.loads(driver.read_text());assert run['status']=='completed'
    assert len(run['trials'])==6 and all(t['status']=='completed' for t in run['trials'])
    for path,expected in run['frozen_sources_and_libraries'].items():assert sha(root/path)==expected
    records=[];bindings=[];saved=0
    for trial in run['trials']:
        directory=root/f'r{trial["repeat"]}_{trial["variant"]}'
        path=directory/'01-真实父反馈四预算完整记录.json';audit_path=directory/'02-完整保存全量精确复审与四预算统计.json'
        assert sha(path)==trial['record_sha256'] and sha(audit_path)==trial['audit_sha256']
        r=json.loads(path.read_text());a=json.loads(audit_path.read_text());assert r['status']==a['status']=='completed'
        assert a['all_saved_published_and_sources_embedded'] and a['all_parent_chains_valid']
        saved+=a['full_audited_objects'];bindings.append(dict(batch=directory.name,record_sha256=sha(path),audit_sha256=sha(audit_path),objects=a['full_audited_objects']))
        assert len(r['routes'])==4 and all(len(route['events'])==route['planned_events']==16 for route in r['routes'])
        records.append((trial,r))
    def stats(values):
        return dict(samples=len(values),mean_ms=float(np.mean(values)),median_ms=float(np.median(values)),
            p95_ms=float(np.percentile(values,95)),maximum_ms=float(np.max(values))) if values else None
    groups=[]
    for variant in ['reference_workers','workers']:
        for budget in [20,50,100,200]:
            events=[e for t,r in records if t['variant']==variant for route in r['routes'] if route['budget_ms']==budget for e in route['events']]
            published=[e for e in events if e['status']=='published_verified'];attempted=[e for e in events if 'maintenance_total_ms' in e]
            groups.append(dict(variant=variant,budget_ms=budget,planned=len(events),published=len(published),
                rejected=sum(e['status']=='source_rejected' for e in events),blocked=sum(e['status'].startswith('blocked') for e in events),
                published_within_budget=sum(not e['budget_overrun'] for e in published),
                published_maintenance=stats([e['maintenance_total_ms'] for e in published]),
                published_cut_and_maintenance=stats([e['cut_and_maintenance_ms'] for e in published]),
                all_attempted_maintenance=stats([e['maintenance_total_ms'] for e in attempted]),
                repair=stats([e['repair']['total_elapsed_ms'] for e in published if e.get('repair')]),
                repair_preparation=stats([e['repair']['preparation_ms'] for e in published if e.get('repair')]),
                quality_operations=sum(len((e.get('maintenance') or {}).get('operations',[])) for e in published
                    if e.get('final_check') and e['final_check']['embedded_closed']),
                quality={str(t):dict(count_gain=sum(e['source_quality'][str(t)]['count']-e['output_quality'][str(t)]['count'] for e in published),
                    count_improved_frames=sum(e['source_quality'][str(t)]['count']>e['output_quality'][str(t)]['count'] for e in published),
                    area_improved_frames=sum(e['source_quality'][str(t)]['area_fraction']>e['output_quality'][str(t)]['area_fraction'] for e in published),
                    area_worse_frames=sum(e['source_quality'][str(t)]['area_fraction']<e['output_quality'][str(t)]['area_fraction'] for e in published),
                    area_gain_sum=sum(e['source_quality'][str(t)]['area_fraction']-e['output_quality'][str(t)]['area_fraction'] for e in published))
                    for t in [10,5,1]}))
    same=root/'02-同源短边修复逐项对拍.json';paired=json.loads(same.read_text());assert paired['pairs']==48
    pairs=[x for row in paired['rows'] for x in row['pairs']]
    same_stats={key:stats([x[key] for x in pairs]) for key in ['reference_ms','compact_ms','reference_preparation_ms','compact_preparation_ms']}
    render_root=root/args.render_name;assert render_root.parent==root
    render=[];render_driver=render_root/'01-私有GPU渲染依赖与完整反馈执行记录.json'
    if render_driver.exists():
        state=json.loads(render_driver.read_text());assert state['status'] in ['completed','failed']
        for path in sorted(render_root.glob('*/01-真实GPU父反馈与像素交付完整记录.json')):
            data=json.loads(path.read_text());assert data['status']=='completed' and len(data['audits'])==len(data['frames'])
            feedback=json.loads((path.parent/'feedback/01-真实父反馈四预算完整记录.json').read_text())
            arrivals={e['step']:e['tool_arrival_perf_counter'] for route in feedback['routes'] for e in route['events']
                if 'tool_arrival_perf_counter' in e}
            ends=[arrivals[x['step']]+x['tool_to_pixels_ms']/1000 for x in data['frames']]
            render.append(dict(batch=path.parent.name,status=data['status'],planned=data['planned_events'],rendered=data['rendered_count'],
                pixels=stats([x['tool_to_pixels_ms'] for x in data['frames']]),
                render=stats([x['publication_render_and_read_ms'] for x in data['frames']]),
                pixel_intervals_with_offline_work=stats([1000*(b-a) for a,b in zip(ends,ends[1:])]),
                all_saved_audits_pass=all(x['check']['embedded_closed'] for x in data['audits']),
                record_sha256=sha(path),renderer_capabilities=data['renderer_capabilities']))
    result=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',planned_events=384,
        driver_sha256=sha(driver),same_source_sha256=sha(same),same_source=same_stats,bindings=bindings,groups=groups,
        full_audited_objects=saved,render_root=str(render_root),render_status=json.loads(render_driver.read_text())['status'] if render_driver.exists() else 'not_started',render=render,
        resource_isolation_not_proven=True,scope='同源组件对拍为逐项等同；完整反馈各自父链，共享设备不作正式隔离速度优势；像素非屏幕呈现')
    target=root/'03-三轮四预算与真实GPU像素终态汇总.json';assert not target.exists()
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
