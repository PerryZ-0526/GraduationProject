"""完整归档五个已结束旧批次；本机核对后才允许删除相同副本。"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile

BASE = Path('/root/autodl-tmp/graduation_project')
WORK = Path('/tmp/graduation_old_backup_20261006_1527')
NAMES = [
    'constrained_20261005_原活动面限定完整154事件反馈_56b33ca6cc7b',
    'constrained_20261005_候选与独立参照同物理清理完整154事件反馈_e4b65b94dd4d',
    'constrained_20261005_清理顺序修复与初态锚点完整154事件反馈_146db594d010',
    'constrained_20261005_物理面积完整154事件反馈_8f822bf54591',
    'constrained_20261004_追加锚点完整能量真实反馈_d38b65c7ead1',
]

def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def inventory(root):
    assert root.parent == BASE and root.name in NAMES
    assert not root.is_symlink() and root.resolve() == root
    files = sorted(root.rglob('*'))
    assert not any(p.is_symlink() for p in files)
    return {p.relative_to(root).as_posix(): {'size': p.stat().st_size, 'sha256': digest(p)}
            for p in files if p.is_file()}

def unused(root):
    # 同时核对命令、工作目录及已打开文件，避免清理实际运行中的批次。
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            command = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            # SSH/SFTP传输服务受系统权限保护，实验子程序仍逐一检查；旧数据另有完整恢复包。
            if command.strip() == '/usr/lib/openssh/sftp-server' or command.strip().startswith('sshd: '):
                continue
            # SSH短命子进程退出时可能先撤销cwd权限；短暂重试，持续拒绝仍停止。
            for retry in range(4):
                try:
                    cwd = os.readlink(proc / 'cwd')
                    break
                except PermissionError:
                    # 已退出、等待回收的僵尸进程没有工作目录或打开文件，不属于活动占用。
                    if '\nState:\tZ' in (proc / 'status').read_text():
                        cwd = None
                        break
                    if retry == 3:
                        raise RuntimeError(json.dumps({'pid': proc.name, 'command': command,
                            'status': (proc / 'status').read_text().splitlines()[:7]}))
                    time.sleep(0.1)
        except FileNotFoundError:
            continue
        if cwd is None:
            continue
        assert str(root) not in command and cwd != str(root) and not cwd.startswith(str(root) + '/')
        for fd in (proc / 'fd').iterdir():
            try:
                name = os.readlink(fd)
            except FileNotFoundError:
                continue
            assert name != str(root) and not name.startswith(str(root) + '/')

def save(name, data):
    # 临时盘写原子快照，数据盘空间不足也能保留操作记录。
    target = WORK / name
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(target)

WORK.mkdir(exist_ok=True)
if sys.argv[1] == 'archive':
    result = {'time_beijing': now(), 'status': 'running', 'batches': []}
    for previous in (WORK / 'manifest.json', WORK / 'manifest_interrupted.json'):
        if previous.exists():
            saved = json.loads(previous.read_text(encoding='utf-8'))
            if len(saved['batches']) > len(result['batches']):
                result['batches'] = saved['batches']
    save('manifest.json', result)
    for i, name in enumerate(NAMES):
        root = BASE / name
        unused(root)
        entries = inventory(root)
        archive = WORK / f'batch_{i}.zip'
        if i < len(result['batches']):
            assert result['batches'][i]['root'] == str(root)
            assert entries == result['batches'][i]['files']
            assert digest(archive) == result['batches'][i]['archive_sha256']
            continue
        if archive.exists():
            # 环境检查中断时只复用完整逐文件成立的归档，不覆盖原文件。
            with zipfile.ZipFile(archive) as z:
                assert set(z.namelist()) == set(entries) and len(z.namelist()) == len(entries)
                for rel, info in entries.items():
                    with z.open(rel) as stream:
                        assert hashlib.file_digest(stream, 'sha256').hexdigest() == info['sha256']
        else:
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
                for rel in entries:
                    z.write(root / rel, rel)
        assert inventory(root) == entries
        unused(root)
        result['batches'].append({'root': str(root), 'archive': str(archive),
                                  'archive_sha256': digest(archive), 'files': entries,
                                  'source_bytes': sum(v['size'] for v in entries.values()),
                                  'archive_bytes': archive.stat().st_size})
        save('manifest.json', result)
    result['status'] = 'completed'
    save('manifest.json', result)
else:
    assert sys.argv[1] == 'delete'
    verified = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    manifest = json.loads((WORK / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['status'] == 'completed' and verified['status'] == 'all_files_verified'
    assert verified['manifest_sha256'] == digest(WORK / 'manifest.json')
    assert verified['manifest_archive_sha256'] == [b['archive_sha256'] for b in manifest['batches']]
    assert verified['verified_file_counts'] == [len(b['files']) for b in manifest['batches']]
    # 删除前重新核对所有原文件，任何变化都停止，不覆盖旧证据。
    for batch in manifest['batches']:
        root = Path(batch['root'])
        unused(root)
        assert inventory(root) == batch['files']
    receipt = {'time_beijing': now(), 'status': 'started',
               'before': shutil.disk_usage(BASE)._asdict(), 'deleted': []}
    save('receipt.json', receipt)
    for batch in manifest['batches']:
        root = Path(batch['root'])
        unused(root)
        shutil.rmtree(root)
        receipt['deleted'].append(str(root))
        save('receipt.json', receipt)
    receipt['after'] = shutil.disk_usage(BASE)._asdict()
    receipt['freed_bytes'] = receipt['after']['free'] - receipt['before']['free']
    receipt['status'] = 'completed'
    save('receipt.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False))
