"""复用17号完整统计口径，绑定本轮实际终态并另列同源邻接组件时间。"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_证书邻接复用完整反馈')
source=BASE/'collect_windows_array_feedback.py'
text=source.read_text(encoding='utf-8')
text=text.replace('20261007_数组源证书本机完整反馈','20261007_证书邻接复用完整反馈')
text=text.replace('09-Windows扫描库身份修订完整链路执行记录.json','03-邻接复用完整四预算与像素执行.json')
begin=text.index("component=json.loads((ROOT/")
end=text.index('report=dict(',begin)
text=text[:begin]+"component=json.loads((ROOT/'02-邻接复用九十六同源与完整提交核对.json').read_text(encoding='utf-8'))\nassert component['status']=='completed' and component['pairs']==96 and component['all_operations_and_arrays_identical']\n"+text[end:]
begin=text.index('    component_pairs=96,')
end=text.index('    resource_isolation_not_proven=',begin)
text=text[:begin]+"    component_pairs=96,global_edge_queries=component['global_edge_queries'],negative_controls=component['negative_controls'],\n    component={name:{field:stats([r[name][field] for r in component['rows']]) for field in ['preparation_ms','total_elapsed_ms']} for name in ['reference','shared']},\n"+text[end:]
text=text.replace('10-本机完整四预算与Arc像素终态汇总.json','04-证书邻接复用完整四预算与Arc像素汇总.json')
actual=ROOT/'collect_shared_topology_actual.py';assert not actual.exists()
actual.write_text(text,encoding='utf-8')
result=subprocess.run([sys.executable,str(actual)],env=dict(os.environ,PYTHONUTF8='1'),capture_output=True,text=True,encoding='utf-8')
log=ROOT/'collect_summary.log';assert not log.exists();log.write_text(result.stdout+result.stderr,encoding='utf-8')
assert result.returncode==0,result.stderr
print(json.dumps(dict(status='completed',actual_collector_sha256=hashlib.sha256(actual.read_bytes()).hexdigest())),flush=True)
