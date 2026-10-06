"""统一完整反馈和像素口径，分组报告长期五方法组件，避免跨硬件相除。"""
from pathlib import Path
import json
import os
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_自适应方向认证完整父反馈')
text=(BASE/'collect_windows_array_feedback.py').read_text(encoding='utf-8')
text=text.replace('20261007_数组源证书本机完整反馈','20261007_自适应方向认证完整父反馈')
text=text.replace('09-Windows扫描库身份修订完整链路执行记录.json','03-自适应方向认证完整四预算与像素执行.json')
begin=text.index("component=json.loads((ROOT/");end=text.index('report=dict(',begin)
text=text[:begin]+"component=json.loads((ROOT/'02-完整长期同源组件控制.json').read_text(encoding='utf-8'))\nassert component['status']=='completed' and component['pairs_per_variant']==33 and component['all_decisions_counts_and_full_results_identical']\n"+text[end:]
begin=text.index('    component_pairs=96,');end=text.index('    resource_isolation_not_proven=',begin)
text=text[:begin]+"    component_pairs_per_variant=33,component_variants=5,\n    component={f'{asset[\"body\"]}_{asset[\"step\"]}':{name:stats([r['comparisons'][name]['total_elapsed_ms'] for r in component['rows'] if r['body']==asset['body'] and r['step']==asset['step']]) for name in ['reference','directional','projected','combined','adaptive']} for asset in component['assets']},\n"+text[end:]
text=text.replace('10-本机完整四预算与Arc像素终态汇总.json','04-自适应方向认证完整时延与质量汇总.json')
actual=ROOT/'collect_adaptive_certificate_actual.py';assert not actual.exists();actual.write_text(text,encoding='utf-8')
run=subprocess.run([sys.executable,str(actual)],env=dict(os.environ,PYTHONUTF8='1'),capture_output=True,text=True,encoding='utf-8')
log=ROOT/'collect_summary.log';assert not log.exists();log.write_text(run.stdout+run.stderr,encoding='utf-8')
assert run.returncode==0,run.stderr
print(json.dumps(dict(status='completed')),flush=True)
