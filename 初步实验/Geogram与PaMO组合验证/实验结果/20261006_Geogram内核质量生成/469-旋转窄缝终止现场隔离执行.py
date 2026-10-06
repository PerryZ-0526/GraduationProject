"""单次诊断固定方法实际负例，记录终止栈与真实生成数组，不发布结果。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
import re
import subprocess
import zipfile

root=Path(__file__).resolve().parent
input_root=Path('/tmp/geogram_native_quality_20261007_23')
folder=root/'rotated_gap_failure_capture_01';folder.mkdir()
capture=folder/'captures';capture.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'))
assert sha(root/'candidate')==build['candidate_binary_sha256']
manifest=json.loads((input_root/'native_inputs.json').read_text('utf8'));case=manifest['cases'][8]
parent=input_root/'inputs/08_parent.obj';tool=input_root/'inputs/08_tool.obj'
assert sha(parent)==case['parent_sha256'] and sha(tool)==case['tool_sha256']
record={'生成时间':now(),'修改时间及修改内容':'首次旋转窄缝实际终止栈和数组现场',
 '文档概述':'评价后已见负例诊断；固定已评价版本不改','索引目录':['native_run','capture_files'],
 'status':'running','parent_sha256':sha(parent),'tool_sha256':sha(tool),'build_sha256':sha(root/'build_record.json')}
path=folder/'01-旋转窄缝隔离终止现场实际记录.json'
def save():
    """诊断终态只根据实际运行，不假设已定位为Triangle或CDT。"""
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save()
try:
    env=dict(os.environ,GEO_NATIVE_FAILURE_CAPTURE=str(capture))
    p=subprocess.run([str(root/'candidate'),str(parent),str(tool),str(folder/'diagnostic.obj')],
                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env,timeout=30)
    log=folder/'native.log';log.write_text(p.stdout,'utf8')
    record['native_run']={'returncode':p.returncode,'log_sha256':sha(log),'diagnostic_result_not_published':True}
    offsets=re.findall(r'libgeogram[^\n]*?\(\+(0x[0-9a-f]+)\)',p.stdout)
    if offsets:
        process=subprocess.run(['addr2line','-f','-C','-e',str(root/'candidate_build/lib/libgeogram.so'),*offsets],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        symbols=folder/'symbols.log';symbols.write_text(process.stdout,'utf8')
        record['symbol_resolution']={'offsets':offsets,'returncode':process.returncode,'log_sha256':sha(symbols)}
    record['capture_files']={str(p.relative_to(folder)):sha(p) for p in sorted(capture.iterdir())}
    record.update(status='completed_actual_rotated_gap_termination_capture',finished_beijing=now());save()
    print('diagnostic_returncode',p.returncode,'captured_files',len(record['capture_files']),flush=True)
except BaseException as error:
    record.update(status='failed_isolated_capture_controller',error=str(error),finished_beijing=now());save();raise
finally:
    with zipfile.ZipFile(root/'rotated_gap_failure_capture_01.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in folder.rglob('*'):
            if p.is_file():archive.write(p,p.relative_to(folder))
