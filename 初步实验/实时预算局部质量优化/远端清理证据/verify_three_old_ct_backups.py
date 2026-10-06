"""核对三批旧CT完整备份的成员、大小及摘要，生成删除依据。"""
from pathlib import Path
import datetime
import hashlib
import json
import zipfile

BASE = Path(__file__).resolve().parent
MANIFEST = BASE / '28-三批旧CT删除前完整文件摘要.json'
ARCHIVES = Path('D:/GraduationProject实验输出/20261006_远端旧CT追加完整备份')
manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
assert manifest['status'] == 'completed' and len(manifest['batches']) == 3
verified = []
for index, batch in enumerate(manifest['batches']):
    path = ARCHIVES / f'batch_{index}.zip'
    assert path.stat().st_size == batch['archive_size']
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == batch['archive_sha256']
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == len(batch['files'])
        assert set(archive.namelist()) == set(batch['files'])
        for rel, info in batch['files'].items():
            assert archive.getinfo(rel).file_size == info['size']
            with archive.open(rel) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == info['sha256']
    verified.append({'root': batch['root'], 'local_archive': str(path),
                     'archive_sha256': digest, 'files': len(batch['files']),
                     'logical_bytes': sum(item['size'] for item in batch['files'].values())})
    print(json.dumps({'batch': index, 'files_verified': len(batch['files'])}), flush=True)
result = {'time_beijing': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
          'status': 'completed', 'all_members_verified': True, 'batches': verified,
          'manifest_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest()}
target = BASE / '29-三批旧CT本机完整备份逐文件核对.json'
assert not target.exists()
target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('ALL_LOCAL_MEMBERS_VERIFIED', flush=True)
