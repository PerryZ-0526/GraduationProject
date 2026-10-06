"""封存本轮实际邻接算法、完整反馈与像素，核查逐成员和上一轮完整前提包。"""
from pathlib import Path
import datetime
import hashlib
import json
import zipfile

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_证书邻接复用完整反馈')
summary=ROOT/'04-证书邻接复用完整四预算与Arc像素汇总.json'
assert json.loads(summary.read_text(encoding='utf-8'))['status']=='completed'
previous=ROOT.parent/'20261007_数组源证书本机完整反馈与Arc像素证据.zip'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


# 上一包保存同字节Geogram、工具、编译依赖及本轮使用的32实际源，不只登记预期摘要。
assert sha(previous)=='2b3c6f2f40b931ff38cac0be3a47d52591e5a981c58b7497cc690275d702776a'
files={p.relative_to(ROOT).as_posix():p for p in ROOT.rglob('*') if p.is_file()
    and not any(part in ['memory_build','__pycache__'] for part in p.relative_to(ROOT).parts)}
for name in ['incremental_mesh_memory_shared_topology.cpp','certificate_activity_edges.py','prepare_shared_topology_feedback.py',
             'verify_shared_topology.py','run_shared_topology_feedback.py','collect_shared_topology_feedback.py','archive_shared_topology_feedback.py']:
    files['controllers/'+name]=BASE/name
manifest=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    summary_sha256=sha(summary),members={name:dict(size=p.stat().st_size,sha256=sha(p)) for name,p in files.items()},
    previous_archive=dict(path=str(previous),sha256=sha(previous),size=previous.stat().st_size),
    scope='本轮完整实际文件；上一轮已核对包为源、工具、Geogram与编译依赖前提，MSVC和Python外部环境仍需对应版本')
archive_path=ROOT.parent/'20261007_证书邻接复用完整反馈与Arc像素证据.zip';assert not archive_path.exists()
with zipfile.ZipFile(archive_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name,p in sorted(files.items()):archive.write(p,name)
    archive.writestr('01-完整成员摘要清单.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(archive_path) as archive:
    assert set(archive.namelist())==set(files)|{'01-完整成员摘要清单.json'} and archive.testzip() is None
    for name,row in manifest['members'].items():
        assert archive.getinfo(name).file_size==row['size']
        with archive.open(name) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256']
receipt=ROOT/'05-本轮完整归档与前提包核对.json';assert not receipt.exists()
result=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='completed',
    archive=str(archive_path),sha256=sha(archive_path),size=archive_path.stat().st_size,members=len(files)+1,
    all_member_sizes_sha256_crc_verified=True,previous_archive=manifest['previous_archive'],summary_sha256=sha(summary))
receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
