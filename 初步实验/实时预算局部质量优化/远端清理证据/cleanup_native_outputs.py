"""只清理已核对归档的原生终态输出，保留供接入使用的库、源码和输入。"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil

root=Path('/root/autodl-tmp/graduation_project/realtime_quality_budget_20261006')
runtime=root/'numeric_native'
inventory=json.loads((root/'cleanup_native_inventory.json').read_text())
plan=json.loads((root/'cleanup_native_verified.json').read_text())
assert plan['all_files_backed_up'] and plan['keep_runtime_library_sources_inputs']
assert plan['delete']==['numeric_native/cpu','numeric_native/cuda','numeric_native_results.zip']
targets=[root/name for name in plan['delete']]
for target in targets:
    # 只允许两个具体输出目录和归档文件；原生运行依赖不进入递归删除范围。
    assert target.resolve().is_relative_to(root.resolve()) and not target.is_symlink()
    if target.is_dir():assert not any(x.is_symlink() for x in target.rglob('*'))
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
    try:
        args=(proc/'cmdline').read_bytes().replace(b'\x00',b' ').decode(errors='replace');cwd=(proc/'cwd').resolve(strict=True)
    except (OSError,RuntimeError):continue
    for target in targets:assert str(target) not in args and target!=cwd and target not in cwd.parents
actual={str(x.relative_to(runtime)) for target in targets[:2] for x in target.rglob('*') if x.is_file()}
assert actual=={x['path'] for x in inventory['files']}
for item in inventory['files']:
    with (runtime/item['path']).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==item['sha256']
with targets[2].open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==plan['archive_sha256']==inventory['archive_sha256']
before=shutil.disk_usage(root)
receipt=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),before=dict(zip(('total','used','free'),before)),deleted=[])
path=root/'cleanup_native_receipt.json'
for target in targets:
    # 逐项保留执行凭据，完整本机备份可恢复原输出。
    if target.is_dir():shutil.rmtree(target)
    else:target.unlink()
    receipt['deleted'].append(str(target));path.write_text(json.dumps(receipt,indent=2))
after=shutil.disk_usage(root);receipt.update(after=dict(zip(('total','used','free'),after)),freed_bytes=after.free-before.free,status='completed')
assert (runtime/'local_separation.so').exists() and (runtime/'native_guard.py').exists() and (runtime/'inputs').is_dir()
path.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
