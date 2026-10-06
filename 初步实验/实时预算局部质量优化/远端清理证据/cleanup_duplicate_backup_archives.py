"""复核本机完整备份后，仅删除六份远端重复临时归档。"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import shutil

root = Path('/tmp/graduation_old_backup_20261006_1527')
plan = json.loads((root / 'cleanup_duplicate_plan.json').read_text())
assert plan['status'] == 'local_archives_reverified'
assert root.resolve() == root and not root.is_symlink()
assert plan['remote_root'] == str(root)
assert {x['remote_name'] for x in plan['files']} == {
    'batch_0.zip', 'batch_1.zip', 'batch_2.zip',
    'batch_3.zip', 'batch_4.zip', 'missing.zip',
}
targets = [root / x['remote_name'] for x in plan['files']]
receipt_path = root / 'duplicate_cleanup_receipt.json'
assert not receipt_path.exists()
for target, entry in zip(targets, plan['files']):
    # 绝对路径、类型和摘要必须全部匹配已复核清单。
    assert target.resolve().parent == root and not target.is_symlink()
    assert target.is_file()
    with target.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == entry['remote_sha256']
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        command = (proc / 'cmdline').read_bytes().replace(b'\x00', b' ').decode(errors='replace')
    except (FileNotFoundError, ProcessLookupError):
        continue
    assert not any(str(target) in command for target in targets)
    try:
        links = [(proc / 'cwd').resolve(strict=True)]
        links += [fd.resolve(strict=True) for fd in (proc / 'fd').iterdir()]
    except (FileNotFoundError, ProcessLookupError):
        continue
    except PermissionError:
        # 系统保护的传输服务不能作为实验占用证明；其余不可读进程阻止删除。
        assert command.strip() in {'/usr/lib/openssh/sftp-server', 'sshd: root@notty'}
        continue
    assert not any(target in links for target in targets)
before = shutil.disk_usage(root)
receipt = {
    'time_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'before': dict(zip(('total', 'used', 'free'), before)),
    'deleted': [], 'status': 'running',
}
for target in targets:
    # 只删除逐项核查的文件，保留目录内全部清单和原始清理记录。
    target.unlink()
    receipt['deleted'].append(str(target))
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
after = shutil.disk_usage(root)
receipt['after'] = dict(zip(('total', 'used', 'free'), after))
receipt['freed_bytes'] = after.free - before.free
receipt['data_disk'] = dict(zip(('total', 'used', 'free'), shutil.disk_usage('/root/autodl-tmp')))
receipt['status'] = 'completed'
receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
print(json.dumps(receipt, ensure_ascii=False))
