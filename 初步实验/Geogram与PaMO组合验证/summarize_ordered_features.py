"""重算小特征完整36分母的全网格及物理工具邻域质量，不隐藏失败。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
import trimesh
from audit_followup_candidate import quality_distribution, sha256
from run_geometry_study import now, save


def quality(mesh, center, radius):
    # 邻域由物理工具及固定0.1毫米余量定义，不随维护结果挑选好面。
    active = np.linalg.norm(mesh.triangles_center-center,axis=1)-radius <= .1
    return dict(all=quality_distribution(mesh),roi=quality_distribution(
        trimesh.Trimesh(mesh.vertices,mesh.faces[active],process=False)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    record_path=args.output/'02-浅磨特征保持审计.json'
    record=json.loads(record_path.read_text(encoding='utf-8'))
    audit_path=args.output/'03-小特征完整分母与保存对象复审.json'
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    if record['status']!='completed_with_recorded_failures' or audit['record_sha256']!=sha256(record_path) or audit['passed']!=audit['artifacts']:
        raise ValueError('完整小特征终态或保存复审未成立')
    tools={r['id']:r for r in json.loads((args.output/'01-小特征浅磨工具冻结.json').read_text(encoding='utf-8'))['rows']}
    audited={(r['case'],r['method']):r for r in audit['rows']}
    result=dict(time_beijing=now(),record_sha256=sha256(record_path),audit_sha256=sha256(audit_path),rows=[],methods={},
        scope='全36条分母及所有实际返回网格；失败保留，0.1毫米邻域不等于特征尺寸证书或连续距离界')
    for row in record['rows']:
        case,method=row['case'],row.get('feature_method',row.get('method'))
        tool=tools[case];source=trimesh.load(args.output/(case+'_input')/'clean_source.obj',process=False)
        item=dict(case=case,method=method,status=row['status'],feature_width_mm=row['feature_width_mm'],
            source=quality(source,np.asarray(tool['center_mm']),tool['radius_mm']))
        evidence=audited[case,method]
        if evidence['kind']=='returned_output':
            output=args.output/(case+'_'+method)/'candidate.obj'
            if sha256(output)!=row['output_sha256']:
                raise ValueError('质量统计前保存对象变化')
            item.update(output=quality(trimesh.load(output,process=False),np.asarray(tool['center_mm']),tool['radius_mm']),
                accepted=evidence['recomputed_accepted'],geometry_to_feature_width_ratio=evidence['geometry_to_feature_width_ratio'])
        else:
            item['output_unavailable_reason']=row['status']
        result['rows'].append(item)
    for method in ('full','global','spatial','boolean'):
        rows=[r for r in result['rows'] if r['method']==method]
        result['methods'][method]=dict(planned=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
            returned=sum('output' in r for r in rows),accepted=sum(r.get('accepted',False) for r in rows))
    save(args.output/'04-小特征全分母质量与相对尺度统计.json',result)
    print(result['methods'])
