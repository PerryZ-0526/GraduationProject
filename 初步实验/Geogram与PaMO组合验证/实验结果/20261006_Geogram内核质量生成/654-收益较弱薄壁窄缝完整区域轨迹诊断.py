"""冻结当前算法，仅开启既有轨迹，保存实际区域结果和禁简化控制。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
import re
import subprocess
import zipfile

root=Path(__file__).resolve().parent
native=Path('/tmp/geogram_native_quality_20261007_32')
inputs=Path('/tmp/geogram_native_quality_20261007_29')
folder=root/'weak_quality_trace_01';folder.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
expected=json.loads((root/'freeze.json').read_text('utf8'))
assert sha(native/'build_record.json')==expected['build_sha256']
assert sha(native/'candidate')==expected['candidate_binary_sha256']
assert sha(native/'candidate_build/lib/libgeogram.so')==expected['candidate_library_sha256']
for name,digest in expected['files'].items():
    if name.startswith('mesh_'):assert sha(native/'candidate_source/src/lib/geogram/mesh'/name)==digest
manifest=json.loads((inputs/'native_inputs.json').read_text('utf8'))
checker=Path('/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis')
assert sha(checker)=='0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
record={'生成时间':now(),'修改时间及修改内容':'首次较弱薄壁窄缝完整区域诊断','文档概述':'当前651源码不改，区域轨迹及禁简化对照仅定位，非正式速度统计',
    '索引目录':['rows'],'status':'running','planned_calls':8,'freeze_sha256':sha(root/'freeze.json'),'input_manifest_sha256':sha(inputs/'native_inputs.json'),'rows':[]}
path=folder/'01-较弱薄壁窄缝完整区域轨迹实际记录.json'
def save():
    """逐调用完成后原子记录真实返回、保存摘要和区域轨迹。"""
    p=path.with_suffix('.tmp');p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');p.replace(path)
save()
try:
    for i in [4,6,8,9]:
        case=manifest['cases'][i]
        parent=inputs/'inputs'/f'{i:02d}_parent.obj';tool=inputs/'inputs'/f'{i:02d}_tool.obj'
        assert sha(parent)==case['parent_sha256'] and sha(tool)==case['tool_sha256']
        for mode in ['current','no_simplify']:
            tag=f'{i:02d}_{mode}';mesh=folder/(tag+'.obj');log=folder/(tag+'.log')
            env=dict(os.environ);env['GEO_NATIVE_QUALITY_TRACE']='1';env.pop('GEO_NATIVE_STAGE_TIMING',None)
            args=[str(native/'candidate'),str(parent),str(tool),str(mesh)]+(['no-simplify'] if mode=='no_simplify' else [])
            run=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env,timeout=30);log.write_text(run.stdout,'utf8')
            row={'case_index':i,'case':case['id'],'mode':mode,'returncode':run.returncode,'log_sha256':sha(log),
                'regions':[json.loads(s) for s in re.findall(r'^NATIVE_QUALITY_REGION (\{.*\})$',run.stdout,re.M)],
                'whole_quality_lines':[s for s in run.stdout.splitlines() if 'QualityBoundary' in s]}
            if run.returncode==0:
                audit=subprocess.run([str(checker),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
                ap=folder/(tag+'_audit.json');ap.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr,'mesh_sha256':sha(mesh)},ensure_ascii=False,indent=2)+'\n','utf8')
                actual=json.loads(audit.stdout) if audit.returncode==0 else None
                row.update(native_timing=json.loads(next(s[len('NATIVE_RESULT '):] for s in run.stdout.splitlines() if s.startswith('NATIVE_RESULT '))),
                    mesh_sha256=sha(mesh),audit_sha256=sha(ap),embedded_closed=bool(actual and actual['embedded_closed']))
            record['rows'].append(row);save();print(i,mode,run.returncode,row.get('embedded_closed'),len(row['regions']),flush=True)
    assert len(record['rows'])==8
    record.update(status='completed_all_eight_frozen_method_trace_calls',finished_beijing=now());save()
except BaseException as error:
    record.update(status='failed_actual_trace_calls',error=str(error),finished_beijing=now());save();raise
finally:
    with zipfile.ZipFile(root/'weak_quality_trace_01.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in folder.iterdir():z.write(p,p.name)
