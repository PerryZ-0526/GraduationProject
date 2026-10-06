"""已见16输入三方法完整交错开发比较，保存全部成功、失败、计时与准确检查。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
import random
import subprocess
import time
import zipfile

root=Path(__file__).resolve().parent
inputs=Path('/tmp/geogram_native_quality_20261007_29')
candidate_root=Path('/tmp/geogram_native_quality_20261007_32')
previous_root=Path('/tmp/geogram_native_quality_20261007_27')
folder=root/'three_method_seen16_01';folder.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
plan=json.loads((root/'plan.json').read_text('utf8'))
manifest=json.loads((inputs/'native_inputs.json').read_text('utf8'))
assert sha(inputs/'native_inputs.json')==plan['input_manifest_sha256']
assert sha(candidate_root/'build_record.json')==plan['candidate_build_sha256']
assert sha(candidate_root/'source_manifest.json')==plan['candidate_source_manifest_sha256']
build=json.loads((candidate_root/'build_record.json').read_text('utf8'))
source=json.loads((candidate_root/'source_manifest.json').read_text('utf8'))
for name,digest in source['files'].items():assert sha(candidate_root/'candidate_source/src/lib/geogram/mesh'/name)==digest
assert sha(candidate_root/'candidate_build/lib/libgeogram.so')==build['candidate_library_sha256']
previous=json.loads((previous_root/'build_record.json').read_text('utf8'))
assert sha(previous_root/'build_record.json')==plan['previous_build_sha256']
assert sha(previous_root/'candidate_build/lib/libgeogram.so')==previous['candidate_library_sha256']
assert sha(Path('/tmp/geogram_native_quality_20261006_02/baseline_build/lib/libgeogram.so'))==build['baseline_library_sha256']
methods={'baseline':candidate_root/'baseline','previous':previous_root/'candidate','candidate':candidate_root/'candidate'}
for method,p in methods.items():assert sha(p)==(previous['candidate_binary_sha256'] if method=='previous' else build[method+'_binary_sha256'])
checker=Path('/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis')
assert sha(checker)=='0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
os.environ.pop('GEO_NATIVE_STAGE_TIMING',None);os.environ.pop('GEO_NATIVE_QUALITY_TRACE',None)
record={'生成时间':now(),'修改时间及修改内容':'首次免重复判定已见16输入三方法交错开发比较',
    '文档概述':'原版、569冻结版及免重复判定副本相同输入交错；全部输出精确检查；输入已见，不算独立评价',
    '索引目录':['preflight','rows'],'status':'running','planned_calls':336,'plan_sha256':sha(root/'plan.json'),
    'affinity':sorted(os.sched_getaffinity(0)),'preflight':[],'rows':[]}
path=folder/'01-免重复判定十六已见三方法实际记录.json'
def save():
    """每次实际调用和同保存对象审计完成后原子落盘。"""
    p=path.with_suffix('.tmp');p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');p.replace(path)
def audit(mesh,output):
    """只检查已保存对象，不把非零退出或失效输出当成功。"""
    result=subprocess.run([str(checker),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
    wrapped={'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'mesh_sha256':sha(mesh)}
    output.write_text(json.dumps(wrapped,ensure_ascii=False,indent=2)+'\n','utf8')
    valid=result.returncode==0 and json.loads(result.stdout)['embedded_closed']
    return {'path':str(output),'sha256':sha(output),'embedded_closed':bool(valid)}
save()
try:
    assert len(manifest['cases'])==16
    for i,case in enumerate(manifest['cases']):
        for role in ['parent','tool']:
            mesh=inputs/'inputs'/f'{i:02d}_{role}.obj';assert sha(mesh)==case[role+'_sha256']
            checked=audit(mesh,folder/f'input_{i:02d}_{role}_audit.json')
            record['preflight'].append({'case_index':i,'role':role,'mesh_sha256':sha(mesh),'audit':checked});save()
            assert checked['embedded_closed']
    rng=random.Random(2026100706)
    for i,case in enumerate(manifest['cases']):
        current=folder/f'{i:02d}';current.mkdir()
        for repeat in range(-1,6):
            order=list(methods);rng.shuffle(order)
            for method in order:
                tag=method+('_warmup' if repeat<0 else f'_r{repeat:02d}')
                mesh=current/(tag+'.obj');log=current/(tag+'.log')
                args=[str(methods[method]),str(inputs/'inputs'/f'{i:02d}_parent.obj'),str(inputs/'inputs'/f'{i:02d}_tool.obj'),str(mesh)]
                start=time.perf_counter()
                try:run=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
                except subprocess.TimeoutExpired as error:
                    raw=error.stdout or '';raw=raw.decode('utf8',errors='replace') if isinstance(raw,bytes) else raw
                    run=subprocess.CompletedProcess(args,124,raw+'\nNATIVE_RESEARCH_TIMEOUT seconds=30\n')
                elapsed=(time.perf_counter()-start)*1000;log.write_text(run.stdout,'utf8')
                row={'case_index':i,'case':case['id'],'method':method,'repeat':repeat,'returncode':run.returncode,'subprocess_wall_ms':elapsed,'log_sha256':sha(log)}
                if run.returncode==0:
                    row.update(native_timing=json.loads(next(s[len('NATIVE_RESULT '):] for s in run.stdout.splitlines() if s.startswith('NATIVE_RESULT '))),
                        mesh_path=str(mesh),mesh_sha256=sha(mesh),audit=audit(mesh,current/(tag+'_audit.json')))
                record['rows'].append(row);save()
                if repeat==0:print(i,method,run.returncode,row.get('native_timing',{}).get('boolean_ms'),row.get('audit',{}).get('embedded_closed'),flush=True)
    assert len(record['rows'])==336
    record.update(status='completed_all_336_seen_input_three_method_attempts',finished_beijing=now());save()
except BaseException as error:
    record.update(status='failed_actual_three_method_comparison',error=str(error),finished_beijing=now());save();raise
finally:
    with zipfile.ZipFile(root/'three_method_seen16_01.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(folder))
