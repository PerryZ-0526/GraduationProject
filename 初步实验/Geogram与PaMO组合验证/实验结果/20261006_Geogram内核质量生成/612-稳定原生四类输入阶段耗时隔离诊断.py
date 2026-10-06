"""阶段诊断单独运行，全部实际输出精确检查，不计为正式速度评价。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
import re
import subprocess
import zipfile

root=Path(__file__).resolve().parent
input_root=Path('/tmp/geogram_native_quality_20261007_29')
reference_root=Path('/tmp/geogram_native_quality_20261007_27')
folder=root/'stage_profile_01';folder.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'))
fixed=json.loads((input_root/'fixed_method.json').read_text('utf8'))
manifest=json.loads((input_root/'native_inputs.json').read_text('utf8'))
assert sha(input_root/'fixed_method.json')==manifest['method_manifest_sha256']
assert sha(root/'candidate')==build['candidate_binary_sha256']
assert sha(root/'candidate_build/lib/libgeogram.so')==build['candidate_library_sha256']
assert sha(reference_root/'candidate')==fixed['method']['candidate_binary_sha256']
assert sha(reference_root/'candidate_build/lib/libgeogram.so')==fixed['method']['candidate_library_sha256']
checker=Path('/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis')
assert sha(checker)=='0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
record={'生成时间':now(),'修改时间及修改内容':'首次四类输入实际分阶段诊断',
 '文档概述':'仅诊断，不新增参数、几何放宽或正式性能结论；同方法正式副本单次参照',
 '索引目录':['rows'],'status':'running','planned_native_calls':20,
 'profile_build_sha256':sha(root/'build_record.json'),'fixed_method_sha256':sha(input_root/'fixed_method.json'),
 'input_manifest_sha256':sha(input_root/'native_inputs.json'),'affinity':sorted(os.sched_getaffinity(0)),
 'diagnosis_sha256':sha(checker),'rows':[]}
path=folder/'01-稳定原生四类输入阶段诊断实际记录.json'
def save():
    """每个实际调用和准确审计落盘，不把计时记录当作几何有效证明。"""
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');temporary.replace(path)
save()
try:
    for i in [13,10,4,7]:
        case=manifest['cases'][i];parent=input_root/'inputs'/f'{i:02d}_parent.obj';tool=input_root/'inputs'/f'{i:02d}_tool.obj'
        assert sha(parent)==case['parent_sha256'] and sha(tool)==case['tool_sha256']
        for repeat in [-2,-1,0,1,2]:
            profile=repeat!=-2;tag=f'{i:02d}_'+('reference' if not profile else ('profile_warmup' if repeat<0 else f'profile_r{repeat:02d}'))
            mesh=folder/(tag+'.obj');log=folder/(tag+'.log')
            env=dict(os.environ);env.pop('GEO_NATIVE_QUALITY_TRACE',None)
            if profile:env['GEO_NATIVE_STAGE_TIMING']='1'
            else:env.pop('GEO_NATIVE_STAGE_TIMING',None)
            binary=(root if profile else reference_root)/'candidate'
            result=subprocess.run([str(binary),str(parent),str(tool),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env,timeout=30)
            log.write_text(result.stdout,'utf8')
            row={'input_index':i,'case':case['id'],'repeat':repeat,'profile':profile,'returncode':result.returncode,
                'parent_sha256':sha(parent),'tool_sha256':sha(tool),'log_sha256':sha(log)}
            if result.returncode==0:
                timing=json.loads(next(s[len('NATIVE_RESULT '):] for s in result.stdout.splitlines() if s.startswith('NATIVE_RESULT ')))
                audit=subprocess.run([str(checker),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
                ap=folder/(tag+'_audit.json');ap.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr},ensure_ascii=False,indent=2)+'\n','utf8')
                geometry=json.loads(audit.stdout) if audit.returncode==0 else None
                row.update(native_timing=timing,mesh_sha256=sha(mesh),audit_sha256=sha(ap),embedded_closed=bool(geometry and geometry['embedded_closed']),
                    stages=[{'stage':name,'ms':float(ms)} for name,ms in re.findall(r'^NATIVE_PROFILE_STAGE (\S+) ([0-9.e+-]+)$',result.stdout,re.M)],
                    coplanar_stages=[{'depth':int(depth),'stage':name,'ms':float(ms)} for depth,name,ms in re.findall(r'^NATIVE_PROFILE_COPLANAR depth=(\d+) (\S+) ([0-9.e+-]+)$',result.stdout,re.M)],
                    triangle_calls=[{'group':int(group),'boundary':bool(int(boundary)),'budget':int(budget),'ms':float(ms)} for group,boundary,budget,ms in re.findall(r'^NATIVE_PROFILE_TRIANGLE group=(\d+) boundary=(\d+) budget=(\d+) ms=([0-9.e+-]+)$',result.stdout,re.M)])
            record['rows'].append(row);save()
            print(i,repeat,result.returncode,row.get('native_timing',{}).get('boolean_ms'),row.get('embedded_closed'),flush=True)
    assert len(record['rows'])==20
    record.update(status='completed_all_twenty_diagnostic_calls',finished_beijing=now());save()
except BaseException as error:
    record.update(status='failed_actual_stage_diagnostic',error=str(error),finished_beijing=now());save();raise
finally:
    with zipfile.ZipFile(root/'stage_profile_01.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in folder.iterdir():archive.write(p,p.name)
