"""只读复算诊断归档；递归阶段不重复相加，正式测速记录保持不变。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import statistics
import zipfile

here=Path(__file__).resolve().parent
archive=here/'616-稳定原生四类输入阶段诊断完整归档.zip'
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    name=next(n for n in z.namelist() if n.endswith('实际记录.json'))
    raw=z.read(name);record=json.loads(raw)
rows=record['rows']
assert record['status']=='completed_all_twenty_diagnostic_calls'
assert len(rows)==record['planned_native_calls']==20
assert all(r['returncode']==0 and r['embedded_closed'] for r in rows)
cases=[]
for index in [13,10,4,7]:
    selected=[r for r in rows if r['input_index']==index]
    assert sorted(r['repeat'] for r in selected)==[-2,-1,0,1,2]
    measured=[r for r in selected if r['repeat']>=0]
    assert all(len(r['stages'])==7 for r in measured)
    stages={s['stage']:statistics.median(next(t['ms'] for t in r['stages'] if t['stage']==s['stage']) for r in measured) for s in measured[0]['stages']}
    sub={}
    for depth in sorted({s['depth'] for r in measured for s in r['coplanar_stages']}):
        names={s['stage'] for r in measured for s in r['coplanar_stages'] if s['depth']==depth}
        sub[str(depth)]={n:statistics.median(next(s['ms'] for s in r['coplanar_stages'] if s['depth']==depth and s['stage']==n) for r in measured) for n in sorted(names)}
    cases.append({'input_index':index,'case':selected[0]['case'],'profile_boolean_median_ms':statistics.median(r['native_timing']['boolean_ms'] for r in measured),
        'stages_median_ms':stages,'coplanar_by_depth_median_ms':sub,
        'triangle_total_median_ms':statistics.median(sum(t['ms'] for t in r['triangle_calls']) for r in measured),
        'triangle_calls':[len(r['triangle_calls']) for r in measured],
        'official_same_method_reference_ms':next(r['native_timing']['boolean_ms'] for r in selected if r['repeat']==-2)})
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
result={'生成时间':now,'修改时间及修改内容':'首次阶段诊断完整归档只读复算','文档概述':'20次实际调用均静态精确通过；三次计时仅诊断，递归按父子区分不重复求和',
    '索引目录':['cases','receipt_reconciliation'],'status':'completed_twenty_diagnostic_calls_verified',
    'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'raw_record_sha256':hashlib.sha256(raw).hexdigest(),
    'actual_calls':20,'exact_valid':20,'cases':cases,
    'receipt_reconciliation':'614号控制器status残留running；其returncode为0，实际归档终态及20条保存审计成立，原记录不改写'}
(here/'618-稳定原生四类阶段诊断完整统计.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
for c in cases:
    print(c['input_index'],round(c['profile_boolean_median_ms'],3),c['stages_median_ms'],c['coplanar_by_depth_median_ms'],c['triangle_total_median_ms'])
