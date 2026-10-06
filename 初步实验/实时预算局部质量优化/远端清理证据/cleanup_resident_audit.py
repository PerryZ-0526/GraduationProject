"""只清理本机摘要核对成立的旧常驻审计副本，不触及运行目录。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime,timezone,timedelta

base=Path('/root/autodl-tmp/graduation_project/realtime_quality_budget_20261006')
plan=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
root=Path(plan['root']);archive=Path(plan['archive'])
assert root==base/'resident_feedback_audit' and archive==base/'resident_feedback_audit_inputs.zip'
assert not root.is_symlink() and root.resolve()==root and not archive.is_symlink()
files=list(root.rglob('*'));assert not any(p.is_symlink() for p in files)
actual={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
assert actual==plan['expected_root_files']
assert hashlib.sha256(archive.read_bytes()).hexdigest()==plan['archive_sha256']
for pid in Path('/proc').iterdir():
    if not pid.name.isdigit() or int(pid.name)==os.getpid():continue
    try:
        command=(pid/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        cwd=os.readlink(pid/'cwd')
    except OSError:continue
    assert not any(str(p) in command or cwd==str(p) or cwd.startswith(str(p)+'/') for p in (root,archive))
receipt={'time_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),
         'before':shutil.disk_usage(base)._asdict(),'deleted':[],'status':'started'}
target=Path('/dev/shm/realtime_resident_cleanup_receipt_20261006.json')
def save():target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
save()
shutil.rmtree(root);receipt['deleted'].append(str(root));save()
archive.unlink();receipt['deleted'].append(str(archive));save()
receipt['after']=shutil.disk_usage(base)._asdict();receipt['freed_bytes']=receipt['after']['free']-receipt['before']['free']
receipt['status']='completed';save();print(json.dumps(receipt))
