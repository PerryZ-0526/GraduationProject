"""三源两区域完整GPU投影，新增原活动域外有向面与固定点保存核对。"""
import argparse
import json
from pathlib import Path
import trimesh
from audit_followup_candidate import sha256
from constrained_quality import fixed_surface_contract
from locality_masks import make_masks
from planar_active_patch import SOURCE
from preserved_controller_source import replace_once
from preserved_feedback_gate import audit_preserved_candidate
from run_initial_encoding_projection import InitialEncodingEngine
from run_geometry_study import now,save


class ActivePatchEngine(InitialEncodingEngine):
    def setup(self):
        info=super().setup()
        source=self.output/'planar_active_patch.py';source.write_text(SOURCE,encoding='utf-8')
        self.sftp.put(str(source),self.remote+'/'+source.name)
        worker=(self.output/'initial_encoding_worker.py').read_text(encoding='utf-8')
        worker=replace_once(worker,'from planar_patch import rebuild_planar_regions','from planar_active_patch import rebuild_planar_regions')
        path=self.output/'active_patch_worker.py';path.write_text(worker,encoding='utf-8')
        self.sftp.put(str(path),self.remote+'/run_constrained_worker.py')
        info['active_patch_source_sha256']={p.name:sha256(p) for p in (source,path)}
        info['generation_scope']='原来源活动面限定种子及邻接传播；保留旧投影及所有数值门控'
        return info

    def run(self,source,labels,tool,method,folder):
        if method=='full':
            # 完整PaMO回退必须保持原算法身份，不能误送活动面生成工作器。
            return super().run(source,labels,tool,method,folder)
        prefix='expanded' if method=='expanded' else 'planar'
        actual=prefix+'_tangent_protected_preserved_geometry_areaguard_active_scope_shared'
        return super().run(source,labels,tool,actual,folder)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pairs','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args()
    old_path=args.pairs/'01-三源三轮四方法同输入比较.json'
    old=json.loads(old_path.read_text(encoding='utf-8'))
    cases=[r for r in old['rows'] if r['declared_method']=='boolean' and r['round']==0]
    if old['status']!='completed_with_recorded_outcomes' or len(cases)!=3:
        raise ValueError('已有三源完整同输入对照缺失')
    args.output.mkdir(exist_ok=False)
    record=dict(time_beijing=now(),status='running',published=False,previous_record_sha256=sha256(old_path),rows=[],
        scope='三份已见开发源各两区域完整GPU投影及外部面契约；无连续父反馈或独立评价')
    result=args.output/'01-活动面限制三源完整GPU投影.json'
    engine=ActivePatchEngine(args.output,args.port)
    try:
        record['environment']=engine.setup();save(result,record)
        for case in cases:
            folder=args.pairs/(case['case']+'_input')
            source=folder/'clean_source.obj';labels=folder/'clean_labels.json';tool=folder/'tool.obj'
            hashes={name:sha256(path) for name,path in (('source.obj',source),('labels.json',labels),('tool.obj',tool))}
            if hashes!=case['same_input_sha256']:
                raise ValueError('冻结开发实际输入变化')
            for method in ('boolean','expanded'):
                target=args.output/(case['case']+'_'+method)
                row=engine.run(source,labels,tool,method,target)
                row=audit_preserved_candidate(engine,source,tool,labels,target,row)
                row.update(case=case['case'],region=method)
                if not row['execution']['returncode']:
                    before=trimesh.load(source,process=False);output=trimesh.load(target/'candidate.obj',process=False)
                    bits=json.loads(labels.read_text(encoding='utf-8'))['operand_bits']
                    active,fixed=make_masks(before,bits,trimesh.load(tool,process=False),'boolean',4 if method=='expanded' else 2,allow_shared=True)
                    contract=fixed_surface_contract(before,output,active,fixed)
                    row['original_activity_external_face_contract']=contract
                    if not contract['passed']:
                        row['status']='original_activity_external_face_contract_rejected'
                record['rows'].append(row);save(result,record)
                print(case['case'],method,row['status'],flush=True)
        record.update(status='completed_with_recorded_outcomes',finished_beijing=now());save(result,record)
    finally:
        engine.close()
