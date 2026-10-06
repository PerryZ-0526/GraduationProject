"""同冻结三源核对活动面限定的CPU生成，尚不含GPU投影或连续发布。"""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from audit_followup_candidate import sha256,quality_distribution
from constrained_quality import fixed_surface_contract
from locality_masks import make_masks,save_obj_fp64
from planar_active_patch import rebuild_planar_regions,SOURCE
from run_geometry_study import now,save
from run_constrained_feedback import global_geometry


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pairs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    record_path=args.pairs/'01-三源三轮四方法同输入比较.json'
    record=json.loads(record_path.read_text(encoding='utf-8'))
    if record['status']!='completed_with_recorded_outcomes':
        raise ValueError('必须使用已有完整同输入对照')
    rows=[r for r in record['rows'] if r['declared_method']=='boolean' and r['round']==0]
    if len(rows)!=3:
        raise ValueError('三源完整分母缺失')
    args.output.mkdir(exist_ok=False)
    (args.output/'planar_active_patch_snapshot.py').write_text(SOURCE,encoding='utf-8')
    report=dict(time_beijing=now(),record_sha256=sha256(record_path),source_sha256=sha256(args.output/'planar_active_patch_snapshot.py'),rows=[],published=False,
        scope='已见三源同输入，仅活动面限制的CPU生成；无GPU投影、连续反馈或独立新输入结论')
    for row in rows:
        folder=args.pairs/(row['case']+'_input')
        source_path=folder/'clean_source.obj';labels_path=folder/'clean_labels.json';tool_path=folder/'tool.obj'
        actual={key:sha256(path) for key,path in (('source.obj',source_path),('labels.json',labels_path),('tool.obj',tool_path))}
        if actual!=row['same_input_sha256']:
            raise ValueError('同次输入摘要变化')
        source=trimesh.load(source_path,process=False);tool=trimesh.load(tool_path,process=False)
        bits=json.loads(labels_path.read_text(encoding='utf-8'))['operand_bits']
        active,fixed=make_masks(source,bits,tool,'boolean',2,allow_shared=True)
        output,labels,details=rebuild_planar_regions(source,bits,active,allow_shared=True,min_area_mm2=1e-12)
        path=args.output/(row['case']+'.obj');save_obj_fp64(output,path)
        contract=fixed_surface_contract(source,output,active,fixed)
        report['rows'].append(dict(case=row['case'],input_sha256=actual,output_sha256=sha256(path),
            active_faces=int(active.sum()),source_faces=len(source.faces),external_contract=contract,
            geometry=global_geometry(output,source),source_quality=quality_distribution(source),
            output_quality=quality_distribution(output),details=details,
            physical_area_valid=bool(np.all(output.area_faces>1e-12))))
    save(args.output/'01-活动面限制三源CPU生成诊断.json',report)
    print([(r['case'],r['external_contract']['passed'],r['geometry']['probe_max_mm']) for r in report['rows']])
