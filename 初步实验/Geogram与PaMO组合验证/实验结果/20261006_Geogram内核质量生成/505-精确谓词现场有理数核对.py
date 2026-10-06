"""从保存的binary64展开项恢复精确有理数，不按浮点容差判定重合。"""
from pathlib import Path
from fractions import Fraction
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
from itertools import combinations

here=Path(__file__).resolve().parent
source=here/'精确谓词全零现场全部输出/captures/predicate_zero_terms.json'
data=json.loads(source.read_text('utf8'))
value=lambda a:sum((Fraction.from_float(x) for x in a),Fraction())
points=[tuple(value(p[k])/value(p['w']) for k in ('x','y')) for p in data['points']]
equal=[[i,j] for i,j in combinations(range(4),2) if points[i]==points[j]]
orientation=[]
for i,j,k in combinations(range(4),3):
    a,b,c=points[i],points[j],points[k]
    det=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    orientation.append({'indices':[i,j,k],'sign':int(det>0)-int(det<0),'exact_zero':det==0})
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次谓词实际展开项精确有理数核对',
 '文档概述':'现场确有重复点，不将四项全零先归因下溢；重复点进入CDT原因待定位',
 '索引目录':['equal_pairs','orientation'],'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'status':'completed_exact_fraction_check_of_captured_predicate',
 'unique_projected_points':len(set(points)),'equal_pairs':equal,'orientation':orientation,
 'points_estimates':[[float(v) for v in p] for p in points]}
target=here/'506-精确谓词实际四点有理数核对记录.json';assert not target.exists()
target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print('unique_points',record['unique_projected_points'],'equal_pairs',equal)
