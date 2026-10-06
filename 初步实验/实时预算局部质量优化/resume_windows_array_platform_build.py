"""保留前两次失败；恢复MSVC默认平台宏并追加UTF-8，不更改几何源码。"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_数组源证书本机完整反馈')
old_path=ROOT/'01-本机同内核独立准备与构建.json'
old=json.loads(old_path.read_text(encoding='utf-8'));assert old['status']=='failed'
assert json.loads((ROOT/'02-显式UTF8私有构建修订.json').read_text(encoding='utf-8'))['status']=='failed'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for row in old['restored'].values():assert sha(ROOT/row['path'])==row['sha256']
script=(ROOT/'prepare_windows_array_feedback_first_failed.py').read_text(encoding='utf-8')
script=script.replace('BASE=Path(__file__).resolve().parent',f'BASE=Path({str(BASE.as_posix())!r})')
script=script.replace('assert not ROOT.exists()','assert ROOT.exists()').replace('ROOT.mkdir()','')
begin=script.index('    with zipfile.ZipFile(ARCHIVE) as archive:');end=script.index("    execute('02_geogram_configure'",begin)
script=script[:begin]+"    record['restored']=json.loads((ROOT/'01-本机同内核独立准备与构建.json').read_text(encoding='utf-8'))['restored']\n"+script[end:]
script=script.replace("'01-本机同内核独立准备与构建.json'\nsha=", "'03-平台宏与UTF8完整私有构建.json'\nsha=")
script=script.replace("'02_geogram_configure'","'02_geogram_configure_platform_utf8'").replace("'03_geogram_build'","'03_geogram_build_platform_utf8'")
script=script.replace("'-DGEOGRAM_WITH_GRAPHICS=OFF'","'-DCMAKE_CXX_FLAGS=/DWIN32 /D_WINDOWS /EHsc /utf-8','-DGEOGRAM_WITH_GRAPHICS=OFF'")
current=ROOT/'prepare_windows_array_feedback_platform_utf8.py';assert not current.exists()
current.write_text(script,encoding='utf-8')
log=ROOT/'resume_platform_utf8_driver.log'
with log.open('x',encoding='utf-8') as stream:
    code=subprocess.run([sys.executable,str(current)],env=dict(os.environ,PYTHONUTF8='1'),stdout=stream,stderr=subprocess.STDOUT).returncode
assert code==0,code
print(json.dumps(dict(status='completed',actual_controller_sha256=sha(current))),flush=True)
