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
# 新边拒绝封存方法实际构建绑定候选修订，原版基线只读复用并核对。
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
fixed=json.loads((root/'fixed_method.json').read_text('utf8'))
assert fixed['status']=='frozen_native_method_after_complete_seen_development_before_future_new_evaluation'
native_root=Path(fixed['method']['remote_root'])
assert sha(native_root/'build_record.json')==fixed['method']['build_sha256']
assert sha(native_root/'source_manifest.json')==fixed['method']['source_manifest_sha256']
for method in ['baseline','candidate']:
    assert sha(root/method)==fixed['method'][method+'_binary_sha256']
assert sha(native_root/'candidate_build/lib/libgeogram.so')==fixed['method']['candidate_library_sha256']
assert sha(Path('/tmp/geogram_native_quality_20261006_02/baseline_build/lib/libgeogram.so'))==fixed['method']['baseline_library_sha256']
for name,digest in fixed['files'].items():
    if name.startswith('mesh_surface_'):
        assert sha(native_root/'candidate_source/src/lib/geogram/mesh'/name)==digest
assert sha(root/'fixed_method.json')==manifest['method_manifest_sha256']

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
    p=output/'01-固定方法十六新参数交错质量速度记录.json'
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


record['planned_native_benchmark_attempts'] = 224
record['native_call_operational_timeout_seconds'] = 30
record['timeout_semantics'] = '到期是本候选执行失败，不算成功输出或质量收益，不重启旧调用'
save()
rng=random.Random(manifest['benchmark']['random_seed'])
try:
    # 全部输入在第一份生成结果出现前准确核查，预审也绑定原冻结摘要。
    for i,case in enumerate(manifest['cases']):
        parent=root/'inputs'/f'{i:02d}_parent.obj'
        tool=root/'inputs'/f'{i:02d}_tool.obj'
        assert sha(parent)==case['parent_sha256'] and sha(tool)==case['tool_sha256']
        for role,mesh in [('parent',parent),('tool',tool)]:
            audit=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
            result=json.loads(audit.stdout) if audit.returncode==0 else None
            entry={'case_index':i,'role':role,'mesh_sha256':sha(mesh),'returncode':audit.returncode,
                   'stdout':audit.stdout,'stderr':audit.stderr}
            record.setdefault('input_preflight',[]).append(entry);save()
            assert result and result['embedded_closed']
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
                # 已记录的失败继续保留，后续不同输入仍按原计划执行。
        # 重复输出的质量全部在本机复算；结构检查先查每方法首份实际保存对象。
        for method in ['baseline','candidate']:
            mesh=folder/(method+'_r00.obj')
            first=next(r for r in record['rows'] if r['case_index']==i and r['method']==method and r['repeat']==0)
            if first['returncode']!=0:continue
            audit=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            p=folder/(method+'_native_audit.json')
            p.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr},ensure_ascii=False,indent=2)+'\n','utf8')
            record['native_audits'].append({'case_index':i,'method':method,'mesh_sha256':sha(mesh),
                                          'audit_path':str(p),'audit_sha256':sha(p),'returncode':audit.returncode})
            save()
    assert len(record['rows'])==224
    record.update(status='completed_all_fixed_method_new_parameter_planned_attempts',finished_beijing=now(),
                  saved_outputs=sum(r['returncode']==0 for r in record['rows']),
                  failed_attempts=sum(r['returncode']!=0 for r in record['rows']))
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
