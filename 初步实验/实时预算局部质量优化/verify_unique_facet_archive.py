"""核对完整唯一面扫描归档及既有前提包，生成不可覆盖的本机记录。"""
from pathlib import Path
import datetime
import hashlib
import json
import zipfile

BASE = Path(__file__).resolve().parent/'诊断证据'
RECEIPT = BASE/'48-唯一面扫描完整远端归档回执.json'
ZIP = Path('C:/Users/24848/Desktop/GraduationProject/tmp/唯一面扫描完整归档/证据.zip')
PREREQUISITES = Path('D:/GraduationProject实验输出/20261006_实时预算局部质量算法/Linux完整连续与资源诊断证据')
receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
assert receipt['status'] == 'completed' and ZIP.stat().st_size == receipt['size']
with ZIP.open('rb') as stream:
    assert hashlib.file_digest(stream,'sha256').hexdigest() == receipt['sha256']
with zipfile.ZipFile(ZIP) as archive:
    manifest = json.loads(archive.read('01-完整成员摘要清单.json'))
    assert set(archive.namelist()) == set(manifest['members']) | {'01-完整成员摘要清单.json'}
    assert len(archive.namelist()) == receipt['members']
    for name, info in manifest['members'].items():
        assert not name.startswith('/') and '..' not in Path(name).parts
        assert archive.getinfo(name).file_size == info['size']
        with archive.open(name) as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest() == info['sha256']
    assert archive.testzip() is None
verified = {}
for name, digest in receipt['prerequisites'].items():
    with (PREREQUISITES/name).open('rb') as stream:
        actual = hashlib.file_digest(stream,'sha256').hexdigest()
    assert actual == digest
    verified[name] = actual
out = BASE/'49-唯一面扫描完整归档逐成员与前提核对.json'
assert not out.exists()
out.write_text(json.dumps({'time_beijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    'status':'completed', 'members_verified':receipt['members'], 'archive_sha256':receipt['sha256'],
    'all_sizes_sha256_crc_verified':True, 'prerequisites_verified':verified},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'members_verified':receipt['members'], 'prerequisites_verified':len(verified)}),flush=True)
