"""从隔离官方镜像寻找远端原版2300文件的精确版本，不修改现有参考库。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import io
import json
import subprocess
import zipfile

here=Path(__file__).resolve().parent
project=next(p for p in here.parents if (p/'研究内容1-创新点.md').is_file())
repo=project/'实验结果/Geogram原生源码只读镜像'
build=json.loads((here/'625-已保留接缝顶点免重复判定原生构建记录.json').read_text('utf8'))
expected=build['baseline_source_hashes']
git=['git','-c','safe.directory='+repo.as_posix(),'-C',str(repo)]
commits=subprocess.check_output(git+['rev-list','--all','--max-count=500'],text=True).splitlines()
probes=['src/lib/geogram/basic/geometry.h','src/lib/geogram/delaunay/CDT_2d.h','src/lib/geogram/numerics/multi_precision.h']
candidates=[];tested=[];matched=None
for commit in commits:
    ok=True
    for name in probes:
        raw=subprocess.check_output(git+['show',commit+':'+name])
        if hashlib.sha256(raw).hexdigest()!=expected[name]:ok=False;break
    if ok:candidates.append(commit)
for commit in candidates:
    raw=subprocess.check_output(git+['archive','--format=zip',commit])
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        differences=[name for name,digest in expected.items() if name not in z.namelist() or hashlib.sha256(z.read(name)).hexdigest()!=digest]
    tested.append({'commit':commit,'different_expected_files':differences})
    if not differences:
        matched=commit
        archive=here/'661-远端原版2300源码同源官方历史归档.zip';assert not archive.exists();archive.write_bytes(raw)
        break
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now,'修改时间及修改内容':'首次官方历史逐字节匹配远端原版源码','文档概述':'目标为冻结实际原版2300份源码，不用同版本号推定相同源代码',
    '索引目录':['tested'],'status':'matched_all_frozen_original_source_files' if matched else 'no_exact_frozen_source_match_in_available_history',
    'expected_files':len(expected),'available_commits':len(commits),'probe_files':probes,'candidate_commits':candidates,'tested':tested,'matching_commit':matched}
if matched:record['archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
(here/'660-官方历史与远端冻结2300源码匹配记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print(record['status'],len(commits),len(candidates),len(tested),matched,flush=True)
