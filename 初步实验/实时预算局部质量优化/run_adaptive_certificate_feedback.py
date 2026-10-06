"""冻结原数组与自适应方向认证，完整四预算父反馈和Arc像素不覆盖历史。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

BASE=Path(__file__).resolve().parent
PROFILE=Path('D:/GraduationProject实验输出/20261007_方向区间与投影源认证对照_v4')
ROOT=Path('D:/GraduationProject实验输出/20261007_自适应方向认证完整父反馈')
controls=PROFILE/'02-五方法准确区间与长期同源终态.json'
assert json.loads(controls.read_text(encoding='utf-8'))['status']=='completed'
assert not ROOT.exists();ROOT.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
build=json.loads((PROFILE/'01-五方法独立编译与资产恢复.json').read_text(encoding='utf-8'))
for member,digest in build['frozen_files'].items():assert sha(PROFILE/member)==digest
for variant,name in [('reference','reference_workers'),('adaptive','workers')]:
    current=ROOT/name;current.mkdir()
    for p in (PROFILE/variant).iterdir():
        if p.is_file():shutil.copyfile(p,current/p.name)
    # 方法身份必须包含实际参与编译的两个新增头文件。
    path=current/'verified_budget_feedback.py';text=path.read_text(encoding='utf-8')
    before="method_names=['certificate_activity_edges.py'";assert text.count(before)==1
    text=text.replace(before,"method_names=['directional_bounds.h','projected_separation.h','certificate_activity_edges.py'")
    path.write_text(text,encoding='utf-8')
    (current/'build_identity.json').write_text(json.dumps(dict(status='completed',libraries=[dict(path=str(p),sha256=sha(p)) for p in current.glob('*.dll')]),ensure_ascii=False,indent=2),encoding='utf-8')
prepared=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='completed',
    actual_profile_sha256=sha(controls),actual_build_sha256=sha(PROFILE/'01-五方法独立编译与资产恢复.json'),
    adaptive_trigger_pairs=32768,certificate_topology_reuse_both_methods=True,
    frozen_files={str(p.relative_to(ROOT)):sha(p) for name in ['workers','reference_workers'] for p in (ROOT/name).iterdir() if p.is_file()})
(ROOT/'01-自适应方向完整反馈准备与实际版本.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(controls,ROOT/'02-完整长期同源组件控制.json')
text=(BASE/'run_shared_topology_feedback.py').read_text(encoding='utf-8')
text=text.replace('20261007_证书邻接复用完整反馈','20261007_自适应方向认证完整父反馈')
text=text.replace('01-私有邻接复用准备与编译.json','01-自适应方向完整反馈准备与实际版本.json')
text=text.replace('02-邻接复用九十六同源与完整提交核对.json','02-完整长期同源组件控制.json')
text=text.replace("controls['pairs']==96","controls['pairs_per_variant']==33 and controls['variants']==5")
text=text.replace('03-邻接复用完整四预算与像素执行.json','03-自适应方向认证完整四预算与像素执行.json')
actual=ROOT/'run_adaptive_certificate_feedback_actual.py';assert not actual.exists()
actual.write_text(text,encoding='utf-8')
with (ROOT/'driver.log').open('x',encoding='utf-8') as log:
    code=subprocess.run([sys.executable,str(actual)],env=dict(os.environ,PYTHONUTF8='1'),stdout=log,stderr=subprocess.STDOUT).returncode
assert code==0,code
print(json.dumps(dict(status='completed',actual_driver_sha256=sha(actual))),flush=True)
