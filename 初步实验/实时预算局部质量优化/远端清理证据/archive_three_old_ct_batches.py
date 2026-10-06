"""备份三个明确结束的旧CT目录，逐文件记录摘要，不修改实验内容。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import zipfile

BASE = Path('/root/autodl-tmp/graduation_project')
NAMES = [
    'constrained_20261004_原固定几何CT真实父反馈_361671540e44',
    'constrained_20261004_逐步独立参照固定几何完整反馈_784fba6ea64f',
    'constrained_20261005_物理面积完整反馈磁盘恢复重跑_89b43280340a',
]
OUT = Path('/tmp/old_ct_backup_additional_20261006')


def stamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def check_idle():
    # 检查命令、工作目录及可读取的打开文件；不终止任何进程。
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            command = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        except OSError:
            continue
        assert not any(name in command for name in NAMES), command
        links = [proc / 'cwd']
        try:
            links.extend((proc / 'fd').iterdir())
        except OSError:
            pass
        for link in links:
            try:
                resolved = os.readlink(link)
            except OSError:
                continue
            assert not any(resolved == str(BASE / name) or resolved.startswith(str(BASE / name) + '/') for name in NAMES), resolved


check_idle()
OUT.mkdir(exist_ok=False)
manifest = {'time_beijing': stamp(), 'status': 'started', 'batches': [], 'data_disk_before': shutil.disk_usage(BASE)._asdict()}
receipt = OUT / 'manifest.json'
receipt.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
for index, name in enumerate(NAMES):
    root = BASE / name
    assert root.is_dir() and root.resolve().parent == BASE and not root.is_symlink()
    paths = sorted(root.rglob('*'))
    assert not any(path.is_symlink() for path in paths)
    archive = OUT / f'batch_{index}.zip'
    entry = {'root': str(root), 'archive': str(archive), 'files': {}}
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as package:
        for path in paths:
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                entry['files'][rel] = {'size': path.stat().st_size, 'sha256': digest}
                package.write(path, rel)
    with archive.open('rb') as stream:
        entry['archive_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    entry['archive_size'] = archive.stat().st_size
    manifest['batches'].append(entry)
    receipt.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'batch': index, 'files': len(entry['files']), 'archive_size': entry['archive_size']}), flush=True)
check_idle()
manifest['status'] = 'completed'
manifest['finished_time_beijing'] = stamp()
receipt.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('BACKUP_COMPLETED', flush=True)
