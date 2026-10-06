"""完整归档本机算法、实际输入输出、失败及像素，逐成员核对，不删除原实验。"""
from pathlib import Path
import datetime
import hashlib
import importlib.metadata
import json
import zipfile

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_数组源证书本机完整反馈')
summary=ROOT/'10-本机完整四预算与Arc像素终态汇总.json'
assert json.loads(summary.read_text(encoding='utf-8'))['status']=='completed'
archive_path=ROOT.parent/'20261007_数组源证书本机完整反馈与Arc像素证据.zip'
assert not archive_path.exists()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
# 编译中间对象可重建，保留实际DLL、完整源码、原控制器、日志与全部实验文件。
files={p.relative_to(ROOT).as_posix():p for p in ROOT.rglob('*') if p.is_file()
       and not any(part in ['geogram_build','memory_build','__pycache__'] for part in p.relative_to(ROOT).parts)}
for name in ['prepare_windows_array_feedback.py','resume_windows_array_feedback_build.py','resume_windows_array_platform_build.py',
             'run_windows_array_feedback.py','resume_windows_array_dll_identity.py','collect_windows_array_feedback.py','archive_windows_array_feedback.py']:
    files['controllers/'+name]=BASE/name
dependencies=BASE.parents[1]/'tmp/实时预算精确整数依赖'
for p in dependencies.rglob('*'):
    if p.is_file():files['source_dependencies/'+p.relative_to(dependencies).as_posix()]=p
versions={name:importlib.metadata.version(name) for name in ['numpy','trimesh','pyvista','vtk','scipy','Pillow']}
manifest=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    summary_sha256=sha(summary),versions=versions,
    members={name:dict(size=p.stat().st_size,sha256=sha(p)) for name,p in files.items()},
    prerequisites={'local_component_archive':'b2040e62a86593cb94801728d0b82a52630c63c4be6b85225eeb5cd8fd9f177b'},
    scope='实际DLL及完整输入输出源码；外部MSVC和Python运行环境仍需同版本，原组件配对输入来自16号完整包')
with zipfile.ZipFile(archive_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name,p in sorted(files.items()):archive.write(p,name)
    archive.writestr('01-完整成员摘要清单.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(archive_path) as archive:
    assert set(archive.namelist())==set(files)|{'01-完整成员摘要清单.json'}
    assert archive.testzip() is None
    for name,row in manifest['members'].items():
        assert archive.getinfo(name).file_size==row['size']
        with archive.open(name) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256']
receipt=ROOT/'11-完整本机归档逐成员核对.json';assert not receipt.exists()
result=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='completed',
    archive=str(archive_path),sha256=sha(archive_path),size=archive_path.stat().st_size,members=len(files)+1,
    all_member_sizes_sha256_crc_verified=True,summary_sha256=sha(summary),prerequisites=manifest['prerequisites'])
receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result),flush=True)
