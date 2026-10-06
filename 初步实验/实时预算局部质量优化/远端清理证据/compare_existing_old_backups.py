"""将既有备份逐文件绑定到远端清单，只下载未覆盖文件。"""
from pathlib import Path
import hashlib
import json

base = Path(__file__).parent
manifest = json.loads((base / '15-五批旧实验完整归档与删除前摘要.json').read_text(encoding='utf-8'))
local = json.loads((base / '18-本机既有五批文件摘要.json').read_text(encoding='utf-8'))
assert manifest['status'] == 'completed' and len(local) == len(manifest['batches']) == 5
all_by_hash = {}
for entry in local:
    for rel, info in entry['files'].items():
        all_by_hash.setdefault((info['sha256'], info['size']), str(Path(entry['local_root']) / rel))
bindings = []
missing = []
for index, (batch, entry) in enumerate(zip(manifest['batches'], local)):
    mapped = {}
    first_archive = Path('D:/GraduationProject实验输出/20261006_远端旧批次完整备份/batch_0.zip')
    if index == 0:
        # 首包已完整下载且归档摘要一致，内部成员会在最终完整核对时再次验证。
        with first_archive.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == batch['archive_sha256']
        bindings.append(mapped)
        continue
    for rel, info in batch['files'].items():
        if entry['files'].get(rel) == info:
            mapped[rel] = str(Path(entry['local_root']) / rel)
        elif (info['sha256'], info['size']) in all_by_hash:
            mapped[rel] = all_by_hash[info['sha256'], info['size']]
        else:
            missing.append({'batch': index, 'relative_path': rel, **info})
    bindings.append(mapped)
result = {'bindings': bindings, 'missing': missing,
          'missing_bytes': sum(row['size'] for row in missing)}
target = base / '19-既有备份绑定与待补文件.json'
assert not target.exists()
target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'mapped_files': [len(row) for row in bindings],
                  'missing_files': len(missing), 'missing_bytes': result['missing_bytes']}))
