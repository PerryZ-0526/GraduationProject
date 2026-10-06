"""原版与候选在相同输入上交错运行，完整保存全部重复输出和结构检查。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import random
import subprocess
import time
import zipfile

root=Path(__file__).resolve().parent
# 第二十一轮实际构建绑定候选修订，原版基线只读复用并核对。
build_path=root/'build_record.json'
build=json.loads(build_path.read_text('utf8'))
assert build['status']=='completed_candidate_build_with_verified_original_baseline_reuse'
manifest=json.loads((root/'native_inputs.json').read_text('utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
output=root/'paired_development_01'
output.mkdir()
allowed=sorted(os.sched_getaffinity(0))
selected=allowed[:manifest['benchmark']['cpu_affinity_logical_processors']]
os.sched_setaffinity(0,selected)
# 正式耗时排除开发轨迹输出，轨迹只在后面的单独调用开启。
os.environ.pop('GEO_NATIVE_QUALITY_TRACE',None)
diagnosis=Path('/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis')
record={'生成时间':now(),'修改时间及修改内容':'首次实际原生生成阶段配对开发与交错耗时',
        '文档概述':'原版默认内部简化与候选内部质量生成；全部重复输出保留',
        '索引目录':['rows','native_audits'],'status':'running','affinity':selected,'allowed_affinity':allowed,
        'input_manifest_sha256':sha(root/'native_inputs.json'),'build_record_sha256':sha(build_path),
        'diagnosis_sha256':sha(diagnosis),'binary_sha256':{},'rows':[],'native_audits':[],'generation_traces':[],'raw_stage_audits':[]}
for method in ['baseline','candidate']:
    assert sha(root/method)==build[method+'_binary_sha256']
    record['binary_sha256'][method]=sha(root/method)


def save():
    """每次重复和审计完成后原子落盘。"""
    p=output/'01-原生十四同输入交错质量速度记录.json'
    tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
    tmp.replace(p)


def native_run(args, **kwargs):
    """限制研究批次的单次运行；到期保留实际部分日志并明确记录失败。"""
    try:
        return subprocess.run(args, timeout=30, **kwargs)
    except subprocess.TimeoutExpired as error:
        partial = error.stdout or ''
        if isinstance(partial, bytes): partial = partial.decode('utf8', errors='replace')
        return subprocess.CompletedProcess(args, 124, partial + '\nNATIVE_RESEARCH_TIMEOUT seconds=30\n')


record['planned_native_benchmark_attempts'] = 196
record['native_call_operational_timeout_seconds'] = 30
record['timeout_semantics'] = '到期是本候选执行失败，不算成功输出或质量收益，不重启旧调用'
save()
rng=random.Random(manifest['benchmark']['random_seed'])
try:
    for i,case in enumerate(manifest['cases']):
        parent=root/'inputs'/f'{i:02d}_parent.obj'
        tool=root/'inputs'/f'{i:02d}_tool.obj'
        assert sha(parent)==case['parent_sha256'] and sha(tool)==case['tool_sha256']
        folder=output/f'{i:02d}'
        folder.mkdir()
        for repeat in range(-1,manifest['benchmark']['repeats_per_method_per_case']):
            order=['baseline','candidate']; rng.shuffle(order)
            for method in order:
                tag=f'{method}_'+('warmup' if repeat<0 else f'r{repeat:02d}')
                mesh=folder/(tag+'.obj')
                log=folder/(tag+'.log')
                start=time.perf_counter()
                process=native_run([str(root/method),str(parent),str(tool),str(mesh)],
                                       stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                elapsed=(time.perf_counter()-start)*1000
                log.write_text(process.stdout,'utf8')
                row={'case_index':i,'case':case['id'],'method':method,'repeat':repeat,
                     'returncode':process.returncode,'subprocess_wall_ms':elapsed,'log_sha256':sha(log)}
                if process.returncode==0:
                    stats=next(line[len('NATIVE_RESULT '):] for line in process.stdout.splitlines() if line.startswith('NATIVE_RESULT '))
                    row.update(native_timing=json.loads(stats),mesh_path=str(mesh),mesh_sha256=sha(mesh))
                record['rows'].append(row); save()
                if repeat==0:
                    print(case['id'],tag,process.returncode,row.get('native_timing',{}).get('boolean_ms'),flush=True)
                if process.returncode: raise RuntimeError('原生生成真实失败，完整保留失败记录')
        # 重复输出的质量全部在本机复算；结构检查先查每方法首份实际保存对象。
        for method in ['baseline','candidate']:
            mesh=folder/(method+'_r00.obj')
            audit=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            p=folder/(method+'_native_audit.json')
            p.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr},ensure_ascii=False,indent=2)+'\n','utf8')
            record['native_audits'].append({'case_index':i,'method':method,'mesh_sha256':sha(mesh),
                                          'audit_path':str(p),'audit_sha256':sha(p),'returncode':audit.returncode})
            save()
    # 另作逐区域诊断，其生成与准确检查成本不进入上面的速度分布。
    for i,case in enumerate(manifest['cases']):
        folder=output/f'{i:02d}'
        mesh=folder/'candidate_trace.obj'
        env=dict(os.environ,GEO_NATIVE_QUALITY_TRACE='1')
        p=native_run([str(root/'candidate'),str(root/'inputs'/f'{i:02d}_parent.obj'),
                          str(root/'inputs'/f'{i:02d}_tool.obj'),str(mesh)],
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env)
        log=folder/'candidate_trace.log';log.write_text(p.stdout,'utf8')
        traces=[json.loads(line[len('NATIVE_QUALITY_REGION '):]) for line in p.stdout.splitlines()
                if line.startswith('NATIVE_QUALITY_REGION ')]
        assert p.returncode==0
        audit=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ap=folder/'candidate_trace_native_audit.json'
        ap.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr},
                                ensure_ascii=False,indent=2)+'\n','utf8')
        record['generation_traces'].append({'case_index':i,'case':case['id'],'returncode':p.returncode,
            'mesh_sha256':sha(mesh),'log_sha256':sha(log),'audit_sha256':sha(ap),'regions':traces,
             'zero_edge_log':[line for line in p.stdout.splitlines() if 'contracted_zero_length_edges=' in line],
            'whole_quality_log':[line for line in p.stdout.splitlines() if 'shared_edges=' in line]})
        save();print('trace',i,len(traces),sum(t['selected'] for t in traces),flush=True)
    # 真实CT另跑禁共面简化，检查零长度收缩本身是否修复原始交线阶段。
    for i in [9,10]:
        folder=output/f'{i:02d}';mesh=folder/'candidate_no_simplify.obj'
        p=native_run([str(root/'candidate'),str(root/'inputs'/f'{i:02d}_parent.obj'),
                          str(root/'inputs'/f'{i:02d}_tool.obj'),str(mesh),'no-simplify'],
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        log=folder/'candidate_no_simplify.log';log.write_text(p.stdout,'utf8');assert p.returncode==0
        audit=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ap=folder/'candidate_no_simplify_native_audit.json'
        ap.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr},
                                ensure_ascii=False,indent=2)+'\n','utf8')
        record['raw_stage_audits'].append({'case_index':i,'mesh_sha256':sha(mesh),'log_sha256':sha(log),
                                         'audit_sha256':sha(ap),'returncode':p.returncode})
        save()
    record.update(status='completed_all_native_paired_development_runs',finished_beijing=now())
    save()
except BaseException as error:
    record.update(status='failed_actual_native_paired_development',error=str(error),finished_beijing=now())
    save()
    raise
finally:
    # 完整包包括全部成功及失败尝试，不只归档最优重复。
    with zipfile.ZipFile(root/'native_paired_development_01.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file(): archive.write(path,path.relative_to(output))
