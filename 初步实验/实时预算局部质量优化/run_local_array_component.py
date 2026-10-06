"""从已核对完整归档复用原实际对象，执行本机96次源证书及翻边后的父链配对。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]/'tmp/数组源证书本机控制_20261006_v2'
ARCHIVE=Path('D:/GraduationProject实验输出/20261006_实时预算局部质量算法/Linux完整连续与资源诊断证据/09-唯一面扫描四预算与GPU像素完整证据.zip')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
controls=json.loads((ROOT/'01-本机数组源证书执行记录.json').read_text(encoding='utf-8'))
assert controls['status']=='completed'
for name,digest in controls['libraries'].items():assert sha(ROOT/name/'incremental_mesh_memory.dll')==digest
assert sha(ARCHIVE)=='298aef40c21ec63345008fcb4524604430c6e3e456428346ce9a4648a6554ba4'
INPUTS=ROOT/'frozen_feedback';INPUTS.mkdir(exist_ok=False)
with zipfile.ZipFile(ARCHIVE) as archive:
    name='tmp/geogram_unique_facets_20261006_flat/r0_flat/01-真实父反馈四预算完整记录.json'
    original=archive.read(name);record=json.loads(original)
    needed={'tmp/geogram_certified_pairs_20261006_r3/inputs/initial.obj'}
    for route in record['routes']:
        if route['budget_ms'] in [100,200]:
            for event in route['events']:
                needed.update(event[key].lstrip('/') for key in ['source_path','output_path'])
    sizes=sum(archive.getinfo(n).file_size for n in needed)
    assert shutil.disk_usage(INPUTS).free>sizes+256*1024**2
    bindings=[]
    for member in sorted(needed):
        assert not member.startswith('/') and '..' not in Path(member).parts
        destination=INPUTS/member;destination.parent.mkdir(parents=True,exist_ok=True)
        with archive.open(member) as source,destination.open('xb') as out:shutil.copyfileobj(source,out)
        bindings.append(dict(member=member,size=destination.stat().st_size,sha256=sha(destination)))
    # 仅将控制副本路径指向逐字节恢复对象；原归档记录及实验身份不覆盖。
    for route in record['routes']:
        if route['budget_ms'] in [100,200]:
            for event in route['events']:
                for key in ['source_path','output_path']:event[key]=str(INPUTS/event[key].lstrip('/'))
    batch=INPUTS/'tmp/geogram_unique_facets_20261006_flat/r0_flat'
    batch.mkdir(parents=True,exist_ok=True)
    (batch/'01-真实父反馈四预算完整记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
script=(BASE/'verify_cached_source_certificate.py').read_text(encoding='utf-8')
# 本机副本显式使用UTF-8读写，保留首版默认编码失败证据。
script=script.replace('.read_text()',".read_text(encoding='utf-8')").replace('indent=2))','indent=2),encoding=\'utf-8\')')
# 同时替换工作器及参照的Linux摘要文件名，实际加载仍是本机私有DLL。
script=script.replace('libincremental_mesh_memory.so','incremental_mesh_memory.dll')
(ROOT/'workers/verify_cached_source_certificate.py').write_text(script,encoding='utf-8')
shutil.copyfile(BASE/'incremental_mesh_memory_array.cpp',ROOT/'workers/incremental_mesh_memory.cpp')
env=dict(os.environ,PYTHONPATH=str(ROOT/'workers')+os.pathsep+str(BASE))
log=ROOT/'component_96_pairs.log'
with log.open('x',encoding='utf-8') as stream:
    code=subprocess.run([sys.executable,str(ROOT/'workers/verify_cached_source_certificate.py'),
                         '--root',str(ROOT),'--batch',str(batch),'--initial',str(INPUTS/'tmp/geogram_certified_pairs_20261006_r3/inputs/initial.obj')],
                        env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    status='completed' if code==0 else 'failed',returncode=code,archive_sha256=sha(ARCHIVE),
    original_record_sha256=hashlib.sha256(original).hexdigest(),objects=bindings,log_sha256=sha(log),
    scope='已见实际反馈输入本机同源对照，非GPU或实时整链结论')
target=ROOT/'08-实际对象恢复与本机配对绑定.json';assert not target.exists()
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert code==0,code
print(json.dumps(dict(status=report['status'],saved_objects=len(bindings))),flush=True)
