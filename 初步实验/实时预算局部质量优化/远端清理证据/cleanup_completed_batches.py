"""仅清理完整备份且核对通过的本线路终态批次，保留删除前后凭据。"""
import datetime
import hashlib
import json
import os
import pathlib
import shutil

ROOT = pathlib.Path('/root/autodl-tmp/graduation_project/realtime_quality_budget_20261006')
EXPECTED = {'budget_20_200', 'sparse_total', 'vectorized_resume', 'verified_ct16', 'targeted_adapter'}
inventory = json.loads((ROOT / 'cleanup_inventory.json').read_text(encoding='utf-8'))
plan = json.loads((ROOT / 'cleanup_verified_plan.json').read_text(encoding='utf-8'))
assert plan['extra_backup_verified'] and not plan['mismatches']
assert set(plan['delete_directories']) == EXPECTED
assert set(plan['delete_archives']) == {name + '_results.zip' for name in EXPECTED - {'budget_20_200'}}
targets = [ROOT / name for name in plan['delete_directories'] + plan['delete_archives']]
for target in targets:
    # 删除前验证绝对路径、符号链接及目录内的链接，不越出明确范围。
    assert target.resolve().parent == ROOT.resolve() and not target.is_symlink()
    if target.is_dir():
        assert not any(item.is_symlink() for item in target.rglob('*'))

for proc in pathlib.Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        args = (proc / 'cmdline').read_bytes().replace(b'\x00', b' ').decode(errors='replace')
        cwd = (proc / 'cwd').resolve(strict=True)
    except (OSError, RuntimeError):
        continue
    # 活动进程引用任一待清目录时拒绝清理，不终止别人的任务。
    for target in targets:
        assert str(target) not in args and target != cwd and target not in cwd.parents

for name in EXPECTED:
    source = ROOT / name
    files = inventory['directories'][name]
    known = {item['path'] for item in files}
    actual = {str(item.relative_to(source)) for item in source.rglob('*')
              if item.is_file() and '__pycache__' not in item.parts}
    assert actual == known
    for item in files:
        path = source / item['path']
        with path.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256']

for item in inventory['archives']:
    path = ROOT / item['path']
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256']

def timestamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

before = shutil.disk_usage(ROOT)
receipt = {'time_beijing': timestamp(), 'root': str(ROOT),
           'before': dict(zip(('total', 'used', 'free'), before)), 'deleted': []}
receipt_path = ROOT / 'cleanup_receipt.json'
for target in targets:
    # 逐项写出进度，即使删除发生环境故障也保留已经完成的操作。
    size = sum(item.stat().st_size for item in target.rglob('*') if item.is_file()) if target.is_dir() else target.stat().st_size
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    receipt['deleted'].append({'path': str(target), 'logical_bytes': size})
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
after = shutil.disk_usage(ROOT)
receipt['after'] = dict(zip(('total', 'used', 'free'), after))
receipt['freed_bytes'] = after.free - before.free
receipt['finished_time_beijing'] = timestamp()
receipt['status'] = 'completed'
receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=True))
