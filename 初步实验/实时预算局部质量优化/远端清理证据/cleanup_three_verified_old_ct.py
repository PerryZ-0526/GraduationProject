"""只删除逐文件本机备份已经验证的三个旧CT目录及重复临时ZIP。"""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import datetime
import os
import subprocess

BASE = Path('/root/autodl-tmp/graduation_project')
BACKUP = Path('/tmp/old_ct_backup_additional_20261006')
NAMES = [
    'constrained_20261004_原固定几何CT真实父反馈_361671540e44',
    'constrained_20261004_逐步独立参照固定几何完整反馈_784fba6ea64f',
    'constrained_20261005_物理面积完整反馈磁盘恢复重跑_89b43280340a',
]
manifest_path = BACKUP / 'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
verified = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert manifest['status'] == verified['status'] == 'completed'
assert verified['all_members_verified']
assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == verified['manifest_sha256']
assert [batch['root'] for batch in manifest['batches']] == [str(BASE / name) for name in NAMES]
assert [batch['root'] for batch in verified['batches']] == [str(BASE / name) for name in NAMES]
targets = [BASE / name for name in NAMES]
transport_exceptions = []
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        command = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
    except FileNotFoundError:
        continue
    assert not any(str(path) in command for path in targets), command
    try:
        links = [proc / 'cwd', *list((proc / 'fd').iterdir())]
        for link in links:
            try:
                resolved = os.readlink(link)
            except FileNotFoundError:
                continue
            assert not any(resolved == str(path) or resolved.startswith(str(path) + '/') for path in targets), resolved
    except PermissionError:
        # 仅允许系统保护的SSH传输服务例外；其他无法核对的进程拒绝删除。
        assert 'sftp-server' in command or command.startswith('sshd:'), command
        transport_exceptions.append({'pid': proc.name, 'command': command})

for index, batch in enumerate(manifest['batches']):
    root = targets[index]
    assert root.resolve().parent == BASE and not root.is_symlink()
    paths = list(root.rglob('*'))
    assert not any(path.is_symlink() for path in paths)
    assert {path.relative_to(root).as_posix() for path in paths if path.is_file()} == set(batch['files'])
    for rel, info in batch['files'].items():
        path = root / rel
        assert path.stat().st_size == info['size']
        with path.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == info['sha256']
    archive = BACKUP / f'batch_{index}.zip'
    assert archive.resolve().parent == BACKUP and not archive.is_symlink()
    with archive.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == batch['archive_sha256'] == verified['batches'][index]['archive_sha256']

def stamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

receipt = {'time_beijing': stamp(), 'status': 'started', 'deleted': [],
           'data_before': shutil.disk_usage(BASE)._asdict(),
           'system_before': shutil.disk_usage('/tmp')._asdict(),
           'protected_transport_processes': transport_exceptions}
record = BACKUP / 'cleanup_receipt.json'
assert not record.exists()
for index, root in enumerate(targets):
    # 每次删除后写回回执，不修改清单或原始实验记录。
    shutil.rmtree(root)
    receipt['deleted'].append(str(root))
    record.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = BACKUP / f'batch_{index}.zip'
    archive.unlink()
    receipt['deleted'].append(str(archive))
    record.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
receipt['data_after'] = shutil.disk_usage(BASE)._asdict()
receipt['system_after'] = shutil.disk_usage('/tmp')._asdict()
receipt['data_freed_bytes'] = receipt['data_after']['free'] - receipt['data_before']['free']
receipt['system_freed_bytes'] = receipt['system_after']['free'] - receipt['system_before']['free']
receipt['finished_time_beijing'] = stamp()
receipt['status'] = 'completed'
receipt['protected_runtime_exists'] = {str(path): path.exists() for path in [
    BASE / 'pamo_quality_20260927_015556_807159_retry3/venv',
    BASE / 'exact_mesh_audit_20261004_0646',
    BASE / 'locality_20261004_021939/geogram_provenance',
    BASE / 'realtime_quality_budget_20261006/numeric_native',
    Path('/tmp/geogram_certified_pairs_20261006_r3'),
    Path('/tmp/compact_short_repair_20261006'),
    Path('/tmp/cached_source_certificate_20261006'),
    Path('/tmp/filtered_source_certificate_20261006'),
]}
receipt['gpu'] = subprocess.check_output([
    'nvidia-smi', '--query-gpu=name,memory.used,utilization.gpu', '--format=csv,noheader'
], text=True)
record.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False), flush=True)
