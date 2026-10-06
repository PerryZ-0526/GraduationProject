"""三源三轮四变体完整消融，去投影单列且不伪造CCD或数值证书。"""
import argparse
import json
from pathlib import Path
import random
import trimesh
from audit_followup_candidate import sha256,quality_distribution
from constrained_quality import fixed_surface_contract
from locality_masks import make_masks
from preserved_controller_source import replace_once
from preserved_feedback_gate import audit_preserved_candidate,check_preserved_mesh
from run_active_patch_projection import ActivePatchEngine
from run_constrained_feedback import global_geometry
from run_geometry_study import execute,now,save


VARIANTS=('complete','without_transition_band','without_external_fixed','without_projection')


def build_variant(source,variant):
    if variant not in VARIANTS:
        raise ValueError('未知消融变体')
    if variant=='without_transition_band':
        source=replace_once(source,'4 if args.method.startswith("expanded") else 2','0')
    elif variant=='without_external_fixed':
        source=replace_once(source,'        fixed = ids >= 0\n        fixed[np.unique(mesh.faces[outside_faces])] = True',
            '        # 消融关闭原顶点与外部面的固定；数值锚点仍按原规则保留。\n'
            '        fixed = np.zeros(len(mesh.vertices), dtype=bool)')
    elif variant=='without_projection':
        start=source.index('        # 新共同来源方法沿用相同切空间求解及完整碰撞投影。')
        end=source.index('        new_fixed = fixed & (ids < 0)',start)
        source=source[:start]+('        # 去投影消融保留质量生成对象，不声称执行CCD。\n'
            '        result = mesh.copy()\n'
            '        projection = {"projection": "disabled_for_ablation", "safe_projection_ms": None}\n')+source[end:]
    compile(source,'active_'+variant,'exec')
    return source


def audit_variant(engine,source,tool,labels,folder,row,variant):
    if row['execution']['returncode']:
        return row
    if variant!='without_projection':
        row=audit_preserved_candidate(engine,source,tool,labels,folder,row)
    before=trimesh.load(source,process=False);mesh=trimesh.load(folder/'candidate.obj',process=False)
    valid,metrics=check_preserved_mesh(engine,folder/'ablation_embedding',mesh,'ablation_output')
    geometry=global_geometry(mesh,before)
    bits=json.loads(labels.read_text(encoding='utf-8'))['operand_bits']
    # 外部评价统一按完整机制两层活动域，不能让去过渡带方法改动评价分母。
    active,fixed=make_masks(before,bits,None,'boolean',2,allow_shared=True)
    external=fixed_surface_contract(before,mesh,active,fixed)
    topology=mesh.euler_number==before.euler_number and len(mesh.split(only_watertight=False))==len(before.split(only_watertight=False))
    geometric=bool(valid and topology and geometry['probe_max_mm']<=.1 and external['passed'])
    row.update(common_geometric_checks_passed=geometric,output_metrics=metrics,
        original_activity_external_face_contract=external,geometry_to_maintenance_source=geometry,
        quality=quality_distribution(mesh),source_quality=quality_distribution(before),
        author_projection_executed=variant!='without_projection',published=False)
    if variant=='without_projection':
        row['status']='geometry_only_passed_without_projection' if geometric else 'geometry_only_rejected_without_projection'
        row['backend_numerical_certificate']='未执行安全投影，不制造数值或CCD证书'
    return row


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pairs','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args()
    previous=args.pairs/'01-三源三轮四方法同输入比较.json'
    old=json.loads(previous.read_text(encoding='utf-8'))
    cases={r['case']:r for r in old['rows'] if r['declared_method']=='boolean' and r['round']==0}
    if old['status']!='completed_with_recorded_outcomes' or len(cases)!=3 or len(old['rows'])!=36:
        raise ValueError('三源同输入完整开发记录缺失')
    args.output.mkdir(exist_ok=False)
    tasks=[(case,round_id,variant) for case in sorted(cases) for round_id in range(3) for variant in VARIANTS]
    random.Random(2026100506).shuffle(tasks)
    record=dict(time_beijing=now(),status='running',published=False,rows=[],schedule=tasks,
        previous_record_sha256=sha256(previous),entry_sha256=sha256(Path(__file__)),
        scope='已见三源各三轮四变体完整分母；去固定仍保留编码和碰撞数值锚点及切平面，不称完全无约束；去投影无CCD证书；共享GPU不推断性能')
    path=args.output/'01-活动面局部机制三轮四变体消融.json'
    engine=ActivePatchEngine(args.output,args.port)
    try:
        record['environment']=engine.setup()
        base=(args.output/'active_patch_worker.py').read_text(encoding='utf-8')
        workers={}
        for variant in VARIANTS:
            worker=args.output/('worker_'+variant+'.py');worker.write_text(build_variant(base,variant),encoding='utf-8');workers[variant]=worker
        record['variant_worker_sha256']={v:sha256(p) for v,p in workers.items()};save(path,record)
        for case,round_id,variant in tasks:
            inputs=args.pairs/(case+'_input')
            source,labels,tool=[inputs/name for name in ('clean_source.obj','clean_labels.json','tool.obj')]
            hashes={name:sha256(p) for name,p in (('source.obj',source),('labels.json',labels),('tool.obj',tool))}
            if hashes!=cases[case]['same_input_sha256']:
                raise ValueError('同输入摘要变化')
            remote=engine.remote+'/run_constrained_worker.py';engine.sftp.put(str(workers[variant]),remote)
            actual=execute(engine.client,['sha256sum',remote])['stdout'].split()[0]
            if actual!=record['variant_worker_sha256'][variant]:
                raise ValueError('实际消融工作器摘要不一致')
            folder=args.output/(case+'_r'+str(round_id)+'_'+variant)
            row=engine.run(source,labels,tool,'boolean',folder)
            row=audit_variant(engine,source,tool,labels,folder,row,variant)
            row.update(case=case,round=round_id,variant=variant,actual_worker_sha256=actual,artifact_directory=str(folder.resolve()))
            record['rows'].append(row);save(path,record)
            print(case,round_id,variant,row['status'],flush=True)
        record.update(status='completed_with_recorded_outcomes',finished_beijing=now());save(path,record)
    finally:
        engine.close()
