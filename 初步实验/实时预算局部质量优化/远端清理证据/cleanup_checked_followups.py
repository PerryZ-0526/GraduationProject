"""仅删除本机归档和保存复审已核对的两个后续终态批次。"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil

root=Path('/root/autodl-tmp/graduation_project/realtime_quality_budget_20261006')
inventory=json.loads((root/'cleanup_followup_inventory.json').read_text())
plan=json.loads((root/'cleanup_followup_verified.json').read_text())
names={'numeric_check_ablation','numeric_range'}
assert plan['all_files_backed_up'] and set(plan['directories'])==names
targets=[root/name for name in sorted(names)]+[root/(name+'_results.zip') for name in sorted(names)]
for target in targets:
    # 检查绝对范围及链接，避免递归操作越出已核查的具体目录。
    assert target.resolve().parent==root.resolve() and not target.is_symlink()
    if target.is_dir():assert not any(x.is_symlink() for x in target.rglob('*'))
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
    try:
        args=(proc/'cmdline').read_bytes().replace(b'\x00',b' ').decode(errors='replace');cwd=(proc/'cwd').resolve(strict=True)
    except (OSError,RuntimeError):continue
    for target in targets:assert str(target) not in args and target!=cwd and target not in cwd.parents
for name in names:
    target=root/name
    files=inventory['directories'][name]
    assert {str(x.relative_to(target)) for x in target.rglob('*') if x.is_file() and '__pycache__' not in x.parts}=={x['path'] for x in files}
    for entry in files:
        with (target/entry['path']).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==entry['sha256']
    with (root/(name+'_results.zip')).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==inventory['archives'][name]
before=shutil.disk_usage(root)
receipt=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),before=dict(zip(('total','used','free'),before)),deleted=[])
path=root/'cleanup_followup_receipt.json'
for target in targets:
    # 逐项保存执行结果，不修改原实验记录或其他线路。
    if target.is_dir():shutil.rmtree(target)
    else:target.unlink()
    receipt['deleted'].append(str(target));path.write_text(json.dumps(receipt,indent=2))
after=shutil.disk_usage(root);receipt['after']=dict(zip(('total','used','free'),after));receipt['freed_bytes']=after.free-before.free;receipt['status']='completed'
path.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
