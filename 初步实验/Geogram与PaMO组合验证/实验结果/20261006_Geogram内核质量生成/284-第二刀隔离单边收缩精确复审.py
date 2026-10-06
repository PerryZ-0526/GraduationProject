"""只核查隔离诊断网格；不将外部收缩冒充原生修复或连续发布。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
root='/tmp/geogram_native_quality_20261006_17/native_scene_contraction_diagnosis_01'
checker='/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis'
mesh=here/'282-第二刀单边隔离诊断网格.obj'
receipt=here/'285-第二刀隔离单边收缩实际复审记录.json'
audit=here/'286-第二刀隔离单边收缩同保存对象精确复审.json'
assert not receipt.exists() and not audit.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now(),'修改时间及修改内容':'首次隔离外部诊断网格精确复审',
 '文档概述':'仅用于定位，不构成原生实现或连续反馈证据','索引目录':['status','mesh_sha256'],
 'status':'started','mesh_sha256':sha(mesh),'checker':checker}
client=remote.connect()
try:
    _,out,_=client.exec_command('mkdir -p '+root);assert out.channel.recv_exit_status()==0
    with client.open_sftp() as sftp:
        sftp.put(str(mesh),root+'/probe.obj')
    _,out,_=client.exec_command('sha256sum '+checker+' '+root+'/probe.obj')
    hashes=out.read().decode();assert out.channel.recv_exit_status()==0
    assert '0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd' in hashes
    assert record['mesh_sha256'] in hashes
    _,out,err=client.exec_command(checker+' '+root+'/probe.obj',timeout=60)
    result=out.read().decode();record['stderr']=err.read().decode()
    record['returncode']=out.channel.recv_exit_status()
    audit.write_text(result,'utf8')
    value=json.loads(result)
    record.update(status='completed_isolated_probe_audit',audit_sha256=sha(audit),
                  audit=value,finished_beijing=now())
    print(json.dumps(value,ensure_ascii=False))
finally:
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
    client.close()
