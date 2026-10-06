"""同输入三轮核对活动面传播限制的单一源码改动与外部契约收益。"""
import argparse
import json
from pathlib import Path
import trimesh
from audit_followup_candidate import quality_distribution,sha256
from constrained_quality import fixed_surface_contract
from locality_masks import make_masks
from planar_active_patch import build_active_source
from preserved_controller_source import replace_once
from run_geometry_study import now,save


def audit(old,new,result):
    if result.exists():
        raise FileExistsError(result)
    old_source=(old/'candidate/planar_patch.py').read_text(encoding='utf-8')
    new_source=(new/'candidate/planar_active_patch.py').read_text(encoding='utf-8')
    old_worker=(old/'candidate/initial_encoding_worker.py').read_text(encoding='utf-8')
    new_worker=(new/'candidate/active_patch_worker.py').read_text(encoding='utf-8')
    # 实际部署副本必须只有两处活动面限制和导入模块替换，不能凭方法名字推断消融。
    if build_active_source(old_source)!=new_source or replace_once(old_worker,
        'from planar_patch import rebuild_planar_regions','from planar_active_patch import rebuild_planar_regions')!=new_worker:
        raise ValueError('实际生成或投影工作器存在未解释的额外改动')
    records=[];selected=[]
    for folder in (old,new):
        path=folder/'01-三源三轮四方法同输入比较.json'
        record=json.loads(path.read_text(encoding='utf-8'))
        if record['status']!='completed_with_recorded_outcomes':
            raise ValueError('完整对照未终态')
        rows={(r['case'],r['round']):r for r in record['rows'] if r['declared_method']=='boolean'}
        if len(rows)!=9 or len(record['rows'])!=36:
            raise ValueError('三源三轮完整分母缺失')
        records.append(dict(path=str(path.resolve()),sha256=sha256(path)));selected.append(rows)
    if set(selected[0])!=set(selected[1]):
        raise ValueError('消融配对案例或轮次不同')
    rows=[]
    for key in sorted(selected[0]):
        pair=dict(case=key[0],round=key[1],variants={})
        if selected[0][key]['same_input_sha256']!=selected[1][key]['same_input_sha256']:
            raise ValueError('不是同一实际输入')
        for variant,folder,record in zip(('unrestricted_coplanar','original_active_faces'),(old,new),selected):
            row=record[key];inputs=folder/(key[0]+'_input')
            paths=dict(source=inputs/'clean_source.obj',labels=inputs/'clean_labels.json',tool=inputs/'tool.obj')
            if {name+'.obj' if name!='labels' else 'labels.json':sha256(path) for name,path in paths.items()}!=row['same_input_sha256']:
                raise ValueError('保存输入摘要变化')
            output=Path(row['artifact_directory'])/'candidate.obj'
            if row['execution']['returncode'] or sha256(output)!=row['output_sha256']:
                raise ValueError('本消融要求实际返回对象且摘要一致')
            source=trimesh.load(paths['source'],process=False);mesh=trimesh.load(output,process=False)
            bits=json.loads(paths['labels'].read_text(encoding='utf-8'))['operand_bits']
            active,fixed=make_masks(source,bits,None,'boolean',2,allow_shared=True)
            pair['variants'][variant]=dict(output_sha256=sha256(output),recorded_status=row['status'],
                external_contract=fixed_surface_contract(source,mesh,active,fixed),quality=quality_distribution(mesh))
        rows.append(pair)
    report=dict(time_beijing=now(),records=records,rows=rows,paired_inputs=9,
        external_contract_passed={v:sum(r['variants'][v]['external_contract']['passed'] for r in rows)
            for v in ('unrestricted_coplanar','original_active_faces')},
        actual_source_change_verified=True,
        scope='已见三源三轮实际同输入与源码单改动消融；各批并非同时运行，不作速度推断；不替代去过渡带、去固定或去投影消融')
    save(result,report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('old','new','result'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(audit(args.old,args.new,args.result)['external_contract_passed'])
