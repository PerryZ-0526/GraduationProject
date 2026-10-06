"""完整封存两个组件批次、两次准备失败和实际反馈，逐成员与前提包核对。"""
from pathlib import Path
import datetime
import hashlib
import json
import zipfile

BASE=Path(__file__).resolve().parent
PARENT=Path('D:/GraduationProject实验输出')
ROOT=PARENT/'20261007_自适应方向认证完整父反馈'
summary=ROOT/'04-自适应方向认证完整时延与质量汇总.json'
assert json.loads(summary.read_text(encoding='utf-8'))['status']=='completed'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


previous=PARENT/'20261007_证书邻接复用完整反馈与Arc像素证据.zip'
assert sha(previous)=='0bb806978be79035fba8d188eaff7de9107bb4ae3b4171a036a209b0f7cab900'
files={}
for prefix,folder in [('feedback',ROOT),('four_variants',PARENT/'20261007_方向区间与投影源认证对照_v3'),
                      ('five_variants',PARENT/'20261007_方向区间与投影源认证对照_v4'),
                      ('first_rejected',PARENT/'20261007_方向区间与投影源认证对照'),
                      ('second_rejected',PARENT/'20261007_方向区间与投影源认证对照_v2')]:
    for p in folder.rglob('*'):
        if p.is_file() and not any(part in ['memory_build','__pycache__'] for part in p.relative_to(folder).parts):
            files[prefix+'/'+p.relative_to(folder).as_posix()]=p
for name in ['directional_bounds.h','projected_separation.h','prepare_directional_certificate.py','prepare_adaptive_certificate.py',
             'profile_directional_certificate.py','profile_adaptive_certificate.py','run_adaptive_certificate_feedback.py',
             'collect_adaptive_certificate_feedback.py','archive_adaptive_certificate_feedback.py']:
    files['controllers/'+name]=BASE/name
manifest=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    summary_sha256=sha(summary),members={name:dict(size=p.stat().st_size,sha256=sha(p)) for name,p in files.items()},
    previous_archive=dict(path=str(previous),size=previous.stat().st_size,sha256=sha(previous)),
    scope='当前完整实际文件，18号及其17号前提包提供Geogram、原CT输入和编译头文件，外部环境仍需对应版本')
archive_path=PARENT/'20261007_自适应方向认证组件与完整反馈证据.zip';assert not archive_path.exists()
with zipfile.ZipFile(archive_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name,p in sorted(files.items()):archive.write(p,name)
    archive.writestr('01-完整成员摘要清单.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(archive_path) as archive:
    assert set(archive.namelist())==set(files)|{'01-完整成员摘要清单.json'} and archive.testzip() is None
    for name,row in manifest['members'].items():
        assert archive.getinfo(name).file_size==row['size']
        with archive.open(name) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256']
receipt=ROOT/'05-完整归档逐成员与前提包核对.json';assert not receipt.exists()
result=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='completed',
    archive=str(archive_path),sha256=sha(archive_path),size=archive_path.stat().st_size,members=len(files)+1,
    all_member_sizes_sha256_crc_verified=True,previous_archive=manifest['previous_archive'],summary_sha256=sha(summary))
receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
