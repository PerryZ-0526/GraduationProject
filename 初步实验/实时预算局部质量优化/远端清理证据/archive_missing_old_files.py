"""只打包既有本机备份尚未覆盖的原文件，绝不改动原批次。"""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

work = Path('/tmp/graduation_old_backup_20261006_1527')
manifest = json.loads((work / 'manifest.json').read_text(encoding='utf-8'))
plan = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
output = work / 'missing.zip'
assert not output.exists() and manifest['status'] == 'completed'
with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
    for row in plan['missing']:
        batch = manifest['batches'][row['batch']]
        rel = row['relative_path']
        assert row['sha256'] == batch['files'][rel]['sha256']
        source = Path(batch['root']) / rel
        assert source.resolve().is_relative_to(Path(batch['root'])) and not source.is_symlink()
        data = source.read_bytes()
        assert len(data) == row['size'] and hashlib.sha256(data).hexdigest() == row['sha256']
        z.writestr(f"{row['batch']}/{rel}", data)
print(json.dumps({'files': len(plan['missing']), 'archive_bytes': output.stat().st_size}))
