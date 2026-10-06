"""真实调用诊断内核，保存被整体拒绝对象和实际边分裂请求。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import subprocess
import zipfile

root=Path(__file__).resolve().parent
output=root/'proposal_capture_01';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'))
assert build['status']=='completed_candidate_build_with_verified_original_baseline_reuse'
assert sha(root/'candidate')==build['candidate_binary_sha256']
manifest=json.loads((root/'native_inputs.json').read_text('utf8'))
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:4])
record={'生成时间':now(),'修改时间及修改内容':'首次捕获孔模型与CT末刀的内部判定前对象',
        '文档概述':'未接受对象仅用于诊断，不发布；启用文件输出的耗时不计正式速度',
        '索引目录':['rows','files'],'status':'running','build_sha256':sha(root/'build_record.json'),
        'input_manifest_sha256':sha(root/'native_inputs.json'),'rows':[]}
path=output/'01-拒绝前对象实际运行记录.json'
def save():
    """每次实际调用保留原始返回码与保存对象摘要。"""
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save()
try:
    for i in [7,10]:
        case=manifest['cases'][i]
        parent=root/'inputs'/f'{i:02d}_parent.obj';tool=root/'inputs'/f'{i:02d}_tool.obj'
        assert sha(parent)==case['parent_sha256'] and sha(tool)==case['tool_sha256']
        env=dict(os.environ,GEO_NATIVE_QUALITY_PROPOSAL_PREFIX=str(output/f'case{i:02d}'),GEO_NATIVE_QUALITY_TRACE='1')
        p=subprocess.run([str(root/'candidate'),str(parent),str(tool),str(output/f'case{i:02d}_returned.obj')],
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env,timeout=30)
        log=output/f'case{i:02d}.log';log.write_text(p.stdout,'utf8')
        record['rows'].append({'case_index':i,'returncode':p.returncode,'log_sha256':sha(log)})
        save();assert p.returncode==0;print('captured',i,flush=True)
    record.update(status='completed_two_actual_internal_proposal_captures',finished_beijing=now(),
                  files={p.name:sha(p) for p in output.iterdir() if p!=path})
    save()
except BaseException as error:
    record.update(status='failed_actual_capture',error=str(error),finished_beijing=now());save();raise
finally:
    with zipfile.ZipFile(root/'proposal_capture_01.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for p in output.iterdir(): archive.write(p,p.name)
