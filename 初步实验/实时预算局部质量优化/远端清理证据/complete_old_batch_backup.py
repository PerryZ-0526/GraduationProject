"""用既有同摘要文件和补充包在D盘组装完整恢复归档，并逐项验证。"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
import zipfile

base = Path(__file__).parent
manifest_path = base / '15-五批旧实验完整归档与删除前摘要.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
plan = json.loads((base / '19-既有备份绑定与待补文件.json').read_text(encoding='utf-8'))
backup = Path('D:/GraduationProject实验输出/20261006_远端旧批次完整备份')
supplement = zipfile.ZipFile(backup / 'missing.zip') if plan['missing'] else None
rows = []
for index, batch in enumerate(manifest['batches']):
    archive = backup / f'batch_{index}.zip'
    if not archive.exists():
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            for rel, info in batch['files'].items():
                local = plan['bindings'][index].get(rel)
                # 本机已有字节与遗漏补充均先核对，再按原相对路径写入可独立恢复的完整包。
                data = Path(local).read_bytes() if local else supplement.read(f'{index}/{rel}')
                assert len(data) == info['size'] and hashlib.sha256(data).hexdigest() == info['sha256']
                z.writestr(rel, data)
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == len(set(z.namelist()))
        assert set(z.namelist()) == set(batch['files'])
        for info in z.infolist():
            assert info.file_size == batch['files'][info.filename]['size']
            with z.open(info) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == batch['files'][info.filename]['sha256']
    with archive.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    rows.append({'root': batch['root'], 'local_archive': str(archive),
                 'files_checked': len(batch['files']), 'local_archive_sha256': sha,
                 'same_archive_bytes_as_remote': sha == batch['archive_sha256']})
    print(json.dumps({'verified_batch': index, 'files': len(batch['files'])}), flush=True)
if supplement:
    supplement.close()
result = {'time_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
          'status': 'all_files_verified',
          'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
          'manifest_archive_sha256': [b['archive_sha256'] for b in manifest['batches']],
          'verified_file_counts': [len(b['files']) for b in manifest['batches']], 'batches': rows,
          'archive_note': '首包直接复制，其余允许本机重组ZIP元数据不同；每个成员字节摘要均与远端一致。'}
output = base / '16-五批完整归档本机逐文件核对.json'
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
