"""核对完整调度分母、实际父链、冻结源码与保存字节，并汇总时间和质量。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
import trimesh
from cadence_policy import POLICIES,maintenance_reason
from audit_followup_candidate import sha256
from run_geometry_study import now,save


def audit(prepared,output):
    manifest=json.loads((prepared/'01-完整范围冻结清单.json').read_text(encoding='utf-8'))
    frozen=json.loads((output/'01-方法与调度冻结.json').read_text(encoding='utf-8'))
    report=json.loads((output/'03-批次环境与完整分母.json').read_text(encoding='utf-8'))
    if report['status']!='completed_with_recorded_outcomes':raise ValueError('批次尚未终态')
    if report['manifest_sha256']!=sha256(prepared/'01-完整范围冻结清单.json'):raise ValueError('冻结清单改变')
    for row in frozen['files']:
        if sha256(output/'runtime'/row['file'])!=row['sha256']:raise ValueError('运行源码改变')
    routes=[r for r in manifest['routes'] if r['split']==frozen['split']]
    for route in routes:
        for item in route['prefix_tools']:
            if sha256(prepared/'inputs'/item['mesh'])!=item['sha256']:raise ValueError('完整工具清单字节改变')
    records=[json.loads(line) for line in (output/'04-逐刀真实父反馈记录.jsonl').read_text(encoding='utf-8').splitlines()]
    indexed={(r['route'],r['round'],r['policy'],r['event']):r for r in records}
    planned=sum(len(r['prefix_tools']) for r in routes)*frozen['rounds']*len(POLICIES)
    if len(indexed)!=len(records) or len(records)!=planned or planned!=report['planned_events']:raise ValueError('完整分母或唯一性不符')
    checks=0;published=0;summaries=[];removal=[]
    for index,route in enumerate(routes):
        initial=prepared/'inputs'/route['initial_mesh']
        if sha256(initial)!=route['initial_mesh_sha256']:raise ValueError('初态改变')
        initial_volume=abs(float(trimesh.load(initial,process=False).volume))
        reference=json.loads((output/f'reference_{index}'/'01-独立累计工具参照.json').read_text(encoding='utf-8'))
        previous_volume=initial_volume
        for position,item in enumerate(reference['rows']):
            if item['status']!='reference_valid':
                previous_volume=None
                removal.append(dict(route=route['id'],event=item['event'],status=item['status'],nominal_increment_mm3=None))
                continue
            source=output/f'reference_{index}'/f'step_{position}'/'source.obj'
            if sha256(source)!=item['source_sha256']:raise ValueError('累计参照保存字节改变')
            volume=abs(float(trimesh.load(source,process=False).volume))
            # 只对相邻有效累计参照统计单次名义去除量，不跨无效参照补算。
            removal.append(dict(route=route['id'],event=item['event'],status=item['status'],
                nominal_increment_mm3=None if previous_volume is None else previous_volume-volume,
                nominal_cumulative_mm3=initial_volume-volume))
            previous_volume=volume
        for repeat in range(frozen['rounds']):
            for policy in POLICIES:
                parent=sha256(initial);pending=0;blocked=False;version=0;baseline=None;rows=[]
                for position,item in enumerate(route['prefix_tools']):
                    row=indexed[(route['id'],repeat,policy,item['event_id'])]
                    folder=output/f'route{index}_round{repeat}_{policy}_step{position}'
                    if json.loads((folder/'audit.json').read_text(encoding='utf-8'))!=row:raise ValueError('逐帧与总账不符')
                    rows.append(row)
                    if blocked:
                        if row['status']!='blocked_by_previous_failure':raise ValueError('失败父链后仍执行')
                    elif row['status']=='blocked_by_previous_failure':
                        # 无效初态允许首帧起全部阻断，须绑定参照审计。
                        reference=json.loads((output/f'reference_{index}'/'01-独立累计工具参照.json').read_text(encoding='utf-8'))
                        if position or reference['initial_valid']:raise ValueError('未证明初态阻断')
                        blocked=True
                    elif row['status']=='reference_unavailable':
                        reference=json.loads((output/f'reference_{index}'/'01-独立累计工具参照.json').read_text(encoding='utf-8'))
                        if any(r['event']==item['event_id'] and r['status']=='reference_valid' for r in reference['rows']):raise ValueError('有效参照误称不可用')
                        blocked=True
                    else:
                        if row['parent_sha256']!=parent:raise ValueError('真实父链不符')
                        if sha256(prepared/'inputs'/item['mesh'])!=row['tool_sha256'] or row['tool_sha256']!=item['sha256']:raise ValueError('真实工具不符')
                        if row.get('frame_wall_ms',0)<=0:raise ValueError('执行帧漏计费用')
                        if 'source_sha256' in row and sha256(folder/'source.obj')!=row['source_sha256']:raise ValueError('源对象改变')
                        if 'source_quality' in row:
                            pending+=1
                            if baseline is None:
                                from audit_followup_candidate import quality_distribution
                                baseline=quality_distribution(trimesh.load(initial,process=False))
                            valid=all((row['source_metrics']['finite'],row['source_metrics']['zero_area_faces']==0,
                                row['source_metrics']['watertight'],row['source_metrics']['winding_consistent'],
                                row['source_metrics']['vertex_manifold_closed'],row['source_metrics'].get('full_exact_embedding_bound',False)))
                            reason=maintenance_reason(policy,pending,row['source_quality'],baseline,position==len(route['prefix_tools'])-1,valid)
                            if reason!=row['maintenance_reason'] or pending!=row['pending_before_maintenance'] or int(bool(reason))!=row['maintenance_calls']:raise ValueError('调度不符')
                            if reason and row['pamo']['returncode']==0:
                                details=json.loads((folder/'details.json').read_text(encoding='utf-8'))
                                if details!=row['pamo']['details'] or details['source_sha256']!=row['source_sha256']:raise ValueError('实际PaMO绑定不符')
                                if details['installed_pamo_sha256']!=report['environment']['pamo_sha256'] or details['extension_sha256']!=report['environment']['extension_sha256']:raise ValueError('实际作者版本改变')
                        if 'candidate_sha256' in row and sha256(folder/'candidate.obj')!=row['candidate_sha256']:raise ValueError('输出字节改变')
                        if row['status']=='published':
                            metrics=row['output_metrics'];certificate=metrics['full_exact_embedding']
                            if not certificate['embedded_closed'] or certificate['saved_sha256']!=row['candidate_sha256']:raise ValueError('发布嵌入证据不符')
                            if not row['expected_topology_matches'] or row['cumulative_geometry']['probe_max_mm']>frozen['geometry_budget_mm']:raise ValueError('发布几何不符')
                            parent=row['candidate_sha256'];version+=1;published+=1
                            if row['maintenance_calls']:pending=0;baseline=row['output_quality']
                        else:blocked=True
                    if row['published_version']!=version:raise ValueError('发布版本不符')
                    checks+=1
                times=[r['frame_wall_ms'] for r in rows if 'frame_wall_ms' in r]
                recorded=next(r for r in report['routes'] if (r['route'],r['round'],r['policy'])==(route['id'],repeat,policy))
                if recorded['published']!=version or recorded['final_parent_sha256']!=parent or abs(recorded['pipeline_wall_ms']-sum(times))>1e-6:raise ValueError('路线总计不符')
                causes=Counter()
                for row in rows:
                    if row['status']!='candidate_audit_rejected':continue
                    metrics=row['output_metrics']
                    for name,failed in (('nonfinite',not metrics['finite']),('area_floor_rejected_faces',metrics['zero_area_faces']>0),
                        ('not_watertight',not metrics['watertight']),('inconsistent_winding',not metrics['winding_consistent']),
                        ('not_vertex_manifold',not metrics['vertex_manifold_closed']),('topology_mismatch',not row['expected_topology_matches']),
                        ('geometry_budget_exceeded',row['cumulative_geometry']['probe_max_mm']>frozen['geometry_budget_mm'])):
                        if failed:causes[name]+=1
                    # 未启动精确检查不等于查出自交；证书失败单独列出。
                    if 'full_exact_embedding' in metrics and not metrics.get('full_exact_embedding_bound',False):causes['exact_embedding_not_certified']+=1
                summaries.append(dict(route=route['id'],round=repeat,policy=policy,complete=version==len(rows),published=version,
                    planned=len(rows),status_counts=dict(Counter(r['status'] for r in rows)),maintenance_calls=sum(r['maintenance_calls'] for r in rows),
                    total_execution_ms=sum(times),executed_frames=len(times),mean_ms=float(np.mean(times)) if times else None,
                    p95_ms=float(np.percentile(times,95)) if times else None,max_ms=max(times) if times else None,
                    gpu_other_process_observed=any(bool(r.get('gpu_processes_before','')) for r in rows),
                    maximum_published_angle10_fraction=max((r['output_quality']['angle_below_10_deg']['fraction'] for r in rows if r['status']=='published'),default=None),
                    maximum_published_angle1_fraction=max((r['output_quality']['angle_below_1_deg']['fraction'] for r in rows if r['status']=='published'),default=None),
                    maximum_published_angle10_area_fraction=max((r['output_quality']['angle_below_10_deg']['area_fraction'] for r in rows if r['status']=='published'),default=None),
                    maximum_published_faces=max((r['output_quality']['total_faces'] for r in rows if r['status']=='published'),default=None),
                    mandatory_repairs=sum(r.get('maintenance_reason')=='mandatory_validity_repair' for r in rows),
                    candidate_rejection_cause_counts=dict(causes),
                    final_flushes=sum(r.get('maintenance_reason')=='final_flush' for r in rows),
                    final_quality=next((r['output_quality'] for r in reversed(rows) if r['status']=='published'),None)))
    result=dict(time_beijing=now(),planned_events=planned,checked_events=checks,published=published,
        ledger_sha256=sha256(output/'04-逐刀真实父反馈记录.jsonl'),summaries=summaries,reference_nominal_removal=removal,
        audit_scope='完整分母、实际父链、源码/输入/保存字节、调度和原证据绑定；不替代重新执行保存几何审计',
        timing_scope=frozen['timing_scope'])
    save(output/'05-完整记录与调度绑定复核.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=audit(args.prepared,args.output)
    print('完整记录复核',result['checked_events'],'发布',result['published'])
