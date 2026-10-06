"""同一已冻结第四刀输入关闭共面简化，定位错误是否发生于该阶段。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import subprocess
import zipfile

root=Path('/tmp/geogram_native_quality_20261006_20')
folder=root/'fourth_scene_raw_stage_diagnostic_01';folder.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'))
binary=root/'candidate';assert sha(binary)==build['candidate_binary_sha256']
parent=root/'native_ct16_feedback_01/e02_candidate.obj'
tool=root/'ct16_inputs/03_tool.obj'
assert sha(parent)=='5946fb4a65f79085482c5e71ca53d6e4d86c51d286ef90621cdfcb93b0347913'
assert sha(tool)=='33e907af1e1b76e4a21e599c9f38e0ddbe21dbdefa153473ae656304c7035bfd'
checker=Path('/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis')
assert sha(checker)=='0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd'
record={'生成时间':now(),'修改时间及修改内容':'首次同源第四刀禁准确共面生成',
 '文档概述':'诊断调用，不计正式速度且不发布','索引目录':['native_run','audit'],
 'status':'running','binary_sha256':sha(binary),'parent_sha256':sha(parent),'tool_sha256':sha(tool),
 'build_sha256':sha(root/'build_record.json')}
path=folder/'01-第四刀禁共面原生保存实际记录.json'
def save():
    """依据实际返回和检查保存诊断终态，不替换连续失败账本。"""
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save()
try:
    mesh=folder/'raw.obj';log=folder/'raw.log'
    p=subprocess.run([str(binary),str(parent),str(tool),str(mesh),'no-simplify'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
    log.write_text(p.stdout,'utf8');record['native_run']={'returncode':p.returncode,'log_sha256':sha(log)}
    if p.returncode==0:
        record['native_run'].update(mesh_sha256=sha(mesh),timing=json.loads(next(line[len('NATIVE_RESULT '):] for line in p.stdout.splitlines() if line.startswith('NATIVE_RESULT '))))
        audit=subprocess.run([str(checker),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
        ap=folder/'raw_audit.json';ap.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr},ensure_ascii=False,indent=2)+'\n','utf8')
        record['audit']={'audit_sha256':sha(ap),'mesh_sha256':sha(mesh),'result':json.loads(audit.stdout)}
    record.update(status='completed_isolated_native_fourth_event_no_simplify_diagnosis',finished_beijing=now());save()
    print(json.dumps(record,ensure_ascii=False),flush=True)
finally:
    with zipfile.ZipFile(root/'fourth_scene_raw_stage_diagnostic_01.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in folder.iterdir():archive.write(p,p.name)
