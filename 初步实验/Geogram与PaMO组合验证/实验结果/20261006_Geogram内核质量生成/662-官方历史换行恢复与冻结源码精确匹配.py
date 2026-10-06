"""原现场含CRLF文件；只接受恢复后逐字节等于冻结摘要的官方源码。"""
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
def restore(raw,digest):
    """仅原字节、统一LF或统一CRLF三项，SHA匹配才允许复用。"""
    lf=raw.replace(b'\r\n',b'\n')
    for label,data in [('raw',raw),('LF',lf),('CRLF',lf.replace(b'\n',b'\r\n'))]:
        if hashlib.sha256(data).hexdigest()==digest:return label,data
    return None,None
commits=subprocess.check_output(git+['rev-list','--all','--max-count=500'],text=True).splitlines()
probes=['src/lib/geogram/basic/geometry.h','src/lib/geogram/delaunay/CDT_2d.h','src/lib/geogram/numerics/multi_precision.h']
candidates=[];tested=[];matched=None;restored={};modes={}
for commit in commits:
    if all(restore(subprocess.check_output(git+['show',commit+':'+name]),expected[name])[0] for name in probes):candidates.append(commit)
for commit in candidates:
    raw=subprocess.check_output(git+['archive','--format=zip',commit])
    restored={};modes={};differences=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=set(z.namelist())
        for name,digest in expected.items():
            mode,data=restore(z.read(name),digest) if name in names else (None,None)
            if mode:restored[name]=data;modes[name]=mode
            else:differences.append(name)
    tested.append({'commit':commit,'different_expected_files':differences})
    if not differences:
        matched=commit;archive=here/'664-远端原版2300源码逐字节恢复归档.zip';assert not archive.exists()
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for name in sorted(restored):z.writestr(name,restored[name])
        break
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now,'修改时间及修改内容':'首次官方源码换行恢复后逐字节核查','文档概述':'只接受2300份恢复字节全部与远端原版冻结SHA一致；旧660未匹配事实保留',
    '索引目录':['tested','restoration_modes'],'status':'matched_all_frozen_original_source_bytes' if matched else 'no_exact_frozen_source_match_after_line_ending_recovery',
    'expected_files':len(expected),'available_commits':len(commits),'candidate_commits':candidates,'tested':tested,'matching_commit':matched}
if matched:record.update(archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),restoration_modes=modes)
(here/'663-官方历史换行恢复与冻结2300源码匹配记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print(record['status'],len(commits),len(candidates),len(tested),matched,flush=True)
