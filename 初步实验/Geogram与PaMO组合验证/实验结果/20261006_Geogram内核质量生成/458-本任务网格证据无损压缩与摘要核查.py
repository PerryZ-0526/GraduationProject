"""仅对本任务目录OBJ启用NTFS透明无损压缩，保留历史原字节与所有文件。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil
import subprocess

here=Path(__file__).resolve().parent
project=here.parents[3]
assert here.is_relative_to(project) and here.name=='20261006_Geogram内核质量生成'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'442-固定方法新参数十六输入运行前冻结清单.json'
fixed=json.loads(manifest.read_text('utf8'))
watched={str(Path(c[role])):c[role+'_sha256'] for c in fixed['cases'] for role in ['parent','tool']}
for path,digest in watched.items():assert sha(Path(path))==digest
record={'生成时间':now(),'修改时间及修改内容':'首次本任务OBJ透明无损压缩',
 '文档概述':'不删除、不移动；仅改变NTFS物理存储，保存摘要复核原字节',
 '索引目录':['status','space','hashes'],'status':'running','absolute_target':str(here),
 'free_before_bytes':shutil.disk_usage(project).free,'hashes':watched}
path=here/'459-本任务网格无损压缩实际执行记录.json';assert not path.exists()
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
p=subprocess.run(['compact.exe','/C','/I','/Q','/S:'+str(here),'*.obj'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
log=here/'460-本任务网格无损压缩实际控制台日志.txt';log.write_bytes(p.stdout)
for source,digest in watched.items():assert sha(Path(source))==digest
record.update(status='completed_transparent_obj_compression_with_32_frozen_input_hashes_unchanged',
 returncode=p.returncode,finished_beijing=now(),free_after_bytes=shutil.disk_usage(project).free,
 log_sha256=sha(log),checked_unchanged_files=len(watched))
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print('transparent_compression',p.returncode,record['free_before_bytes'],record['free_after_bytes'])
