"""消融完整36分母保存几何复审，不把去投影几何检查冒充CCD。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import trimesh
from audit_followup_candidate import sha256,quality_distribution
from constrained_quality import fixed_surface_contract
from locality_masks import make_masks
from preserved_saved_binding import collect_certificates,mesh_valid_saved_binding
from run_active_patch_ablation import VARIANTS,build_variant
from run_constrained_feedback import global_geometry
from run_geometry_study import now,save


def require_complete(record):
    schedule=[tuple(task) for task in record['schedule']]
    rows=[(r['case'],r['round'],r['variant']) for r in record['rows']]
    cases={task[0] for task in schedule}
    expected={(case,round_id,variant) for case in cases for round_id in range(3) for variant in VARIANTS}
    if record['status']!='completed_with_recorded_outcomes' or len(cases)!=3 or len(schedule)!=36 or len(rows)!=36 or set(schedule)!=expected or set(rows)!=expected:
        raise ValueError('三源三轮四变体未完整终态或分母重复缺失')


def no_projection_identity(row):
    # 共用取回器可能登记未执行诊断的占位值；只有明确未通过、无轨迹才等同无证书。
    return row['author_projection_executed'] is False and row['projection']=='disabled_for_ablation' and row.get('numerical_diagnostic') in (
        None,dict(passed=False,trace_available=False))


def recheck(pairs,output,result_path):
    if result_path.exists():
        raise FileExistsError(result_path)
    path=output/'01-活动面局部机制三轮四变体消融.json'
    record=json.loads(path.read_text(encoding='utf-8'));require_complete(record)
    previous=pairs/'01-三源三轮四方法同输入比较.json'
    if sha256(previous)!=record['previous_record_sha256'] or sha256(output/'run_active_patch_ablation.py')!=record['entry_sha256']:
        raise ValueError('开发记录或实际入口摘要变化')
    base=(output/'active_patch_worker.py').read_text(encoding='utf-8')
    for variant in VARIANTS:
        worker=output/('worker_'+variant+'.py')
        if sha256(worker)!=record['variant_worker_sha256'][variant] or worker.read_text(encoding='utf-8')!=build_variant(base,variant):
            raise ValueError('变体工作器不是已登记的单因素改动')
    certificates=collect_certificates(record);rows=[]
    for row in record['rows']:
        case=row['case'];variant=row['variant'];folder=output/(case+'_r'+str(row['round'])+'_'+variant)
        inputs=pairs/(case+'_input')
        source_path=inputs/'clean_source.obj';labels_path=inputs/'clean_labels.json';tool_path=inputs/'tool.obj'
        hashes={name:sha256(p) for name,p in (('source.obj',source_path),('labels.json',labels_path),('tool.obj',tool_path))}
        if hashes!=row['inputs_sha256'] or row['actual_worker_sha256']!=record['variant_worker_sha256'][variant] or str(folder.resolve())!=row['artifact_directory']:
            raise ValueError('实际输入、工作器或返回目录绑定不符')
        item=dict(case=case,round=row['round'],variant=variant,recorded_status=row['status'])
        if row['execution']['returncode']:
            log=folder/'worker.log'
            item.update(kind='execution_failure_evidence',passed=bool(row['status']=='execution_failed' and log.is_file() and log.stat().st_size),
                worker_log_sha256=sha256(log))
        else:
            saved=folder/'candidate.obj';mesh=trimesh.load(saved,process=False);source=trimesh.load(source_path,process=False)
            valid,metrics=mesh_valid_saved_binding(mesh,certificates)
            geometry=global_geometry(mesh,source)
            topology=mesh.euler_number==source.euler_number and len(mesh.split(only_watertight=False))==len(source.split(only_watertight=False))
            bits=json.loads(labels_path.read_text(encoding='utf-8'))['operand_bits']
            active,fixed=make_masks(source,bits,None,'boolean',2,allow_shared=True)
            contract=fixed_surface_contract(source,mesh,active,fixed)
            geometric=bool(valid and topology and geometry['probe_max_mm']<=.1 and contract['passed'])
            # 共同几何结论与GPU执行身份分别核对；无投影不要求不存在的CCD证书。
            identity=row['author_projection_executed']==(variant!='without_projection')
            if variant=='without_projection':
                identity=identity and no_projection_identity(row)
            item.update(kind='returned_output',passed=bool(sha256(saved)==row['output_sha256'] and geometric==row['common_geometric_checks_passed']
                and contract==row['original_activity_external_face_contract'] and identity),
                common_geometric_checks_passed=geometric,metrics=metrics,geometry=geometry,external_contract=contract,
                output_sha256=sha256(saved),quality=quality_distribution(mesh),source_quality=quality_distribution(source))
        rows.append(item)
    report=dict(time_beijing=now(),record_sha256=sha256(path),rows=rows,artifacts=36,passed=sum(r['passed'] for r in rows),
        methods={v:dict(statuses=dict(Counter(r['recorded_status'] for r in rows if r['variant']==v)),
            geometric_passed=sum(r.get('common_geometric_checks_passed',False) for r in rows if r['variant']==v)) for v in VARIANTS},
        scope='完整36分母、实际源码与输入绑定、保存几何和精确嵌入证据复审；不重放GPU求导或CCD、不赋予去投影后端证书、不证明连续距离')
    save(result_path,report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pairs','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--result',type=Path,required=True)
    args=parser.parse_args();report=recheck(args.pairs,args.output,args.result)
    print(report['passed'],'/',report['artifacts'],report['methods'])
    if report['passed']!=report['artifacts']:
        raise SystemExit(1)
