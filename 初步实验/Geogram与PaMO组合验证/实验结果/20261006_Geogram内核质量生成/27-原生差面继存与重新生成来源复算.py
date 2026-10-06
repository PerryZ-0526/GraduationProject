"""按输入完整三角形的坐标集合区分继存差面与重新生成差面，不混为因果证明。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
manifest_path=here/'18-原生十一同输入开发与速度运行前清单.json'
manifest=json.loads(manifest_path.read_text('utf8'))
summary_path=here/'25-原生十一同输入质量几何与速度复算.json'
summary=json.loads(summary_path.read_text('utf8'))
folder=here/'原生同输入全部重复输出'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def triangle_key(triangle):
    """只忽略三角形顶点排列，双精度坐标值不使用舍入容差。"""
    return tuple(sorted(tuple(float(x) for x in p) for p in triangle))


def triangles(path):
    """读取原始保存对象，不焊接或删除面。"""
    mesh=trimesh.load(path,process=False,force='mesh')
    return np.asarray(mesh.vertices)[np.asarray(mesh.faces)]


rows=[]
for i,case in enumerate(manifest['cases']):
    original=set()
    for key in ['parent','tool']:
        assert sha(case[key])==case[key+'_sha256']
        original.update(triangle_key(t) for t in triangles(case[key]))
    row={'case':case['id'],'methods':{}}
    for method in ['baseline','candidate']:
        path=folder/f'{i:02d}'/(method+'_r00.obj')
        ts=triangles(path)
        area=np.linalg.norm(np.cross(ts[:,1]-ts[:,0],ts[:,2]-ts[:,0]),axis=1)/2
        angle=[]
        for k in range(3):
            a,b=ts[:,(k+1)%3]-ts[:,k],ts[:,(k+2)%3]-ts[:,k]
            angle.append(np.degrees(np.arctan2(np.linalg.norm(np.cross(a,b),axis=1),np.einsum('ij,ij->i',a,b))))
        minimum=np.min(angle,axis=0)
        bad=(minimum<10)&(area>0)&np.isfinite(area)
        inherited=np.array([triangle_key(t) in original for t in ts],dtype=bool)
        row['methods'][method]={'output_sha256':sha(path),'bad_complete_input_triangles':int((bad&inherited).sum()),
            'bad_regenerated_triangles':int((bad&~inherited).sum()),
            'regenerated_bad_area_mm2':float(area[bad&~inherited].sum())}
        assert int(bad.sum())==summary['cases'][i]['methods'][method]['quality']['below_10_faces']
    rows.append(row)
    print(case['id'],row['methods'],flush=True)
out={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
     '修改时间及修改内容':'首次原生输出完整输入面继存及重新生成差面核对',
     '文档概述':'重新生成不等于纯切削因果；原背景面重划也会进入该类别',
     '索引目录':['rows'],'status':'completed_eleven_input_triangle_inheritance_checks',
     'source_quality_sha256':sha(summary_path),'input_manifest_sha256':sha(manifest_path),'rows':rows}
(here/'28-原生差面继存与重新生成来源核对.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf8')
