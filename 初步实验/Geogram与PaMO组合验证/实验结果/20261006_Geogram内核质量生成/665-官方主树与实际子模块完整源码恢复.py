"""主树换行和已有子模块仅在匹配冻结SHA时复用，构成同源2300文件。"""
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
reference=project/'reference/近期强基线_20260908/geogram'
build=json.loads((here/'625-已保留接缝顶点免重复判定原生构建记录.json').read_text('utf8'))
expected=build['baseline_source_hashes'];commit='130442ff0f0c069d48ab4ebb4012218f3d861cf2'
git=['git','-c','safe.directory='+repo.as_posix(),'-c','core.excludesFile='+str(repo/'info/exclude'),'-C',str(repo)]
raw=subprocess.check_output(git+['archive','--format=zip',commit])
restored={};provenance={};unresolved=[]
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    names=set(z.namelist())
    for name,digest in expected.items():
        if name in names:
            original=z.read(name);lf=original.replace(b'\r\n',b'\n')
            options=[('official_raw',original),('official_LF',lf),('official_CRLF',lf.replace(b'\n',b'\r\n'))]
        else:options=[]
        if (reference/name).is_file():options.append(('local_exact_frozen_dependency', (reference/name).read_bytes()))
        matched=next(((label,data) for label,data in options if hashlib.sha256(data).hexdigest()==digest),None)
        if matched:provenance[name]=matched[0];restored[name]=matched[1]
        else:unresolved.append(name)
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now,'修改时间及修改内容':'首次主树及既有依赖恢复完整同源源码','文档概述':'主树和第三方文件逐字节匹配实际2300源码摘要；不是仅比较版本名或声称完整子模块提交身份',
    '索引目录':['provenance','unresolved'],'status':'matched_all_2300_frozen_original_bytes' if not unresolved else 'unresolved_actual_source_bytes',
    'official_main_tree_commit':commit,'expected_files':len(expected),'matched_files':len(restored),'unresolved':unresolved,'provenance':provenance,
    'prior_failed_match_records':['660-官方历史与远端冻结2300源码匹配记录.json','663-官方历史换行恢复与冻结2300源码匹配记录.json']}
if not unresolved:
    archive=here/'667-完整2300份同源原版源码归档.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted(restored):z.writestr(name,restored[name])
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(expected)==2300
        assert all(hashlib.sha256(z.read(name)).hexdigest()==digest for name,digest in expected.items())
    record['archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
(here/'666-完整主树与依赖2300同源源码恢复记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print(record['status'],len(restored),len(unresolved))
assert not unresolved
