"""保留诊断头部字节错误，单独解码轴编号并精确核对实际插点。"""
from pathlib import Path
from fractions import Fraction
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import math

here=Path(__file__).resolve().parent
folder=here/'精确插点缓存现场全部输出'
value=lambda a:sum((Fraction.from_float(x) for x in a),Fraction())
rows=[]
for source in sorted((folder/'captures').glob('cdt_insert_*.jsonl')):
    raw=source.read_text('utf8').splitlines()
    # 原诊断coord_index_t按字符写出，显式解码0/1/2三种字节，原文件绝不改写。
    header=raw[0]
    for axis in range(3):header=header.replace(chr(axis),str(axis))
    data=[json.loads(header)]+[json.loads(s) for s in raw[1:] if s]
    if data[-1].get('completed'):continue
    u,v=data[0]['u'],data[0]['v'];points={};indices={};duplicates=[]
    for r in data[1:]:
        if 'before_insert' in r:
            identifier=r['before_insert']
            q=tuple(value(a)/value(r['w']) for a in r['xyz'])
            duplicates.extend([[prior,identifier] for prior,p in points.items() if (p[u],p[v])==(q[u],q[v])])
            points[identifier]=q
        if 'after_insert' in r:indices[r['after_insert']]=r['cdt_index']
    pairs=[]
    for a,p in points.items():
        for b,q in points.items():
            if a>=b:continue
            distance=math.sqrt(sum(float(x-y)**2 for x,y in zip(p,q)))
            bound=128*math.ulp(1.0)*max(abs(float(z)) for z in p+q)
            if distance<=bound:
                pairs.append({'vertex_ids':[a,b],'cdt_indices':[indices.get(a),indices.get(b)],
                    'exact_3d_equal':p==q,'exact_projected_equal':(p[u],p[v])==(q[u],q[v]),
                    'distance_mm':distance,'machine_bound_mm':bound})
    rows.append({'trace_file':source.name,'trace_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'projection_axes':[u,v],'before_insert_count':len(points),'returned_insert_count':len(indices),
        'exact_projection_duplicates':duplicates,'machine_near_point_pairs':pairs,
        'last_unreturned_insert':data[-1].get('before_insert')})
log=folder/'native.log'
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次精确插点记录有理数复审和原诊断头部错误单列',
 '文档概述':'谓词现场重复不能等同插点列表重复；缓存无观测差异不构成一般正确证明',
 '索引目录':['unfinished_traces','limitations'],'status':'completed_actual_cdt_insert_trace_rational_check',
 'header_encoding_issue':'原头部投影轴以单字节字符0/1/2保存，未经解码不能作为合法JSON读取；这里只解码副本，原字节摘要保留',
 'trace_files':len(list((folder/'captures').glob('cdt_insert_*.jsonl'))),
 'cache_mismatch_observations':log.read_text('utf8').count('CDT_CACHE_MISMATCH'),
 'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'unfinished_traces':rows,
 'limitations':'完整失败原因尚未唯一证明；保守拒绝新边版本只检验撤回该类不合格生成方案能否解除本例终止'}
target=here/'551-实际插点近点与缓存有理数复审记录.json';assert not target.exists()
target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print('unfinished',len(rows),'near_pairs',sum(len(r['machine_near_point_pairs']) for r in rows))
