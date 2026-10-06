"""配对已有冻结库，实际记录作者原有阶段日志以定位额外生成成本。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
import subprocess
import zipfile

root=Path(__file__).resolve().parent
prior=Path('/tmp/geogram_native_quality_20261006_02')
output=root/'stage_diagnosis_01';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'))
assert build['status']=='completed_candidate_build_with_verified_original_baseline_reuse'
manifest=json.loads((root/'native_inputs.json').read_text('utf8'))
record={'生成时间':now(),'修改时间及修改内容':'首次绑定原库执行作者阶段计时',
        '文档概述':'开启日志的诊断，不属于正式交错速度样本',
        '索引目录':['compile','rows'],'status':'running','build_sha256':sha(root/'build_record.json'),
        'driver_source_sha256':sha(root/'stage_driver.cpp'),'compile':[],'rows':[]}
path=output/'01-实际原生阶段定位记录.json'
def save():
    """记录真实编译和执行，库摘要不一致直接拒绝。"""
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save();os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
try:
    for method in ['baseline','candidate']:
        source=(prior if method=='baseline' else root)/(method+'_source')
        lib=(prior if method=='baseline' else root)/(method+'_build')/'lib'
        assert sha(lib/'libgeogram.so')==build[method+'_library_sha256']
        binary=output/method
        args=['g++','-O3','-std=c++17',str(root/'stage_driver.cpp'),'-I'+str(source/'src/lib'),
              '-L'+str(lib),'-Wl,-rpath,'+str(lib),'-lgeogram','-o',str(binary)]
        p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        log=output/(method+'_compile.log');log.write_text(p.stdout,'utf8')
        record['compile'].append({'method':method,'returncode':p.returncode,'argv':args,'log_sha256':sha(log)})
        save();assert p.returncode==0
    for i in [0,3,5,7,9,10]:
        for method in ['baseline','candidate']:
            parent=root/'inputs'/f'{i:02d}_parent.obj';tool=root/'inputs'/f'{i:02d}_tool.obj'
            assert sha(parent)==manifest['cases'][i]['parent_sha256'] and sha(tool)==manifest['cases'][i]['tool_sha256']
            p=subprocess.run([str(output/method),str(parent),str(tool),str(output/f'{i:02d}_{method}.obj')],
                             stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
            log=output/f'{i:02d}_{method}.log';log.write_text(p.stdout,'utf8')
            record['rows'].append({'case_index':i,'method':method,'returncode':p.returncode,'log_sha256':sha(log)})
            save();assert p.returncode==0;print(i,method,'stage_diagnosis_complete',flush=True)
    record.update(status='completed_twelve_actual_author_stage_diagnoses',finished_beijing=now(),
                  files={p.name:sha(p) for p in output.iterdir() if p!=path});save()
except BaseException as error:
    record.update(status='failed_actual_author_stage_diagnosis',error=str(error),finished_beijing=now());save();raise
finally:
    with zipfile.ZipFile(root/'stage_diagnosis_01.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for p in output.iterdir():archive.write(p,p.name)
