"""本机中断后核实原始远端记录，完整归档直接复算，避免重复解包。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import zipfile

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
archive=here/'531-新边拒绝三十已见回归全部实际输出.zip'
sha=lambda data:hashlib.sha256(data).hexdigest()
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    entry='01-新边拒绝三十已见输入交错质量速度记录.json'
    actual=json.loads(z.read(entry));assert len(actual['rows'])==420
    for row in actual['rows']:
        if row['returncode']==0:
            name=f"{row['case_index']:02d}/"+Path(row['mesh_path']).name
            assert sha(z.read(name))==row['mesh_sha256']
    print('archive_complete_verified',len(actual['rows']),sum(r['returncode']==0 for r in actual['rows']),flush=True)
client=remote.connect()
try:
    with client.open_sftp() as sftp:
        path='/tmp/geogram_native_quality_20261007_27/native_ct16_feedback_01/01-原生CT十六刀反馈实际记录.json'
        data=sftp.file(path,'rb').read()
        local=here/'553-新边拒绝CT磁盘中断时远端原始记录.json';assert not local.exists();local.write_bytes(data)
        ct=json.loads(data)
finally:client.close()
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次本机磁盘中断及远端实际终态核实',
 '文档概述':'420原生调用已完成；本机部分解包保留，完整ZIP逐对象摘要成立；CT原账本不覆盖',
 '索引目录':['development','ct'],'status':'completed_readonly_actual_remote_and_archive_verification',
 'development':{'archive_sha256':sha(archive.read_bytes()),'planned':420,'returned':sum(r['returncode']==0 for r in actual['rows']),
 'failed':sum(r['returncode']!=0 for r in actual['rows']),'archive_crc_all_valid':True,'all_returned_mesh_sha256_matched':True},
 'ct':{'source_record_sha256':sha(data),'status':ct['status'],'recorded_events':len(ct['events']),
 'accepted_events':sum(r['status']=='accepted_native_output' for r in ct['events']),
 'error':ct.get('error'),'last_event_index':ct['events'][-1]['event_index']},
 'partial_extraction_policy':'不重新生成、不删除或覆盖部分解包现场；质量及几何复算直接读取完整原ZIP'}
(here/'555-本机磁盘中断及原始归档核实记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print('ct',record['ct'],flush=True)
source=(here/'533-新边拒绝三十已见全部质量几何速度复算.py').read_text('utf8')
source=source.replace('import vtk','import vtk\nimport io\nimport zipfile')
source=source.replace("record=json.loads(record_path.read_text('utf8'))",'''archive=zipfile.ZipFile(here/'531-新边拒绝三十已见回归全部实际输出.zip')
record=json.loads(archive.read(record_path.name))
base_trimesh=trimesh
class ArchivedMeshReader:
    """读取完整归档的原字节，不依赖中断后的部分解包文件。"""
    def load(self,path,**kwargs):
        path=Path(path)
        if path.is_relative_to(folder):
            return base_trimesh.load(io.BytesIO(archive.read(path.relative_to(folder).as_posix())),file_type='obj',**kwargs)
        return base_trimesh.load(path,**kwargs)
trimesh=ArchivedMeshReader()''')
source=source.replace("sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()",'''def sha(p):
    """生成输出从完整ZIP读取并逐字节核查；其他输入仍核对原文件。"""
    data=archive.read(p.relative_to(folder).as_posix()) if p.is_relative_to(folder) else p.read_bytes()
    return hashlib.sha256(data).hexdigest()''')
(here/'556-新边拒绝三十已见原始压缩包直接复算.py').write_text(source,'utf8')
