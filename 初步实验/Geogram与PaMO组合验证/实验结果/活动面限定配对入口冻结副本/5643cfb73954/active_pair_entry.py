"""三份冻结开发源三轮交错四方法比较，失败与输入前提均计完整分母。"""
import argparse
import json
from pathlib import Path
import random
import numpy as np
import trimesh
from audit_followup_candidate import sha256
from locality_masks import save_obj_fp64
from ordered_physical_cleanup import clean_for_backend, SOURCE
from preserved_feedback_gate import local_fp64_valid
from run_constrained_batch import HERE
from active_patch_comparisons import ActiveFeatureEngines as FeatureEngines
from run_geometry_study import now, save


METHODS=('full','global','spatial','boolean')


def schedule(ids):
    tasks=[(case,round_id,method) for case in ids for round_id in range(3) for method in METHODS]
    random.Random(2026100504).shuffle(tasks)
    return tasks


class PairEngines(FeatureEngines):
    def setup(self):
        info=dict(baseline=self.baseline.setup(),candidate=self.candidate.setup())
        names=('run_ordered_pairs.py','run_ordered_features.py','ordered_physical_cleanup.py')
        for name in names:
            (self.output/name).write_bytes((HERE/name).read_bytes())
        snapshot=self.output/'ordered_physical_cleanup_snapshot.py'
        snapshot.write_text(SOURCE,encoding='utf-8')
        info['pair_sources_sha256']={name:sha256(self.output/name) for name in (*names,snapshot.name)}
        return info


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('cases','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args()
    manifest_path=args.cases/'01-冻结清单.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for item in manifest['files']:
        path=(args.cases/item['file']).resolve()
        if not path.is_relative_to(args.cases.resolve()) or sha256(path)!=item['sha256']:
            raise ValueError('冻结配对输入变化或跨包引用')
    args.output.mkdir(exist_ok=False)
    cases={};preconditions={}
    for case in manifest['cases']:
        folder=args.output/(case['id']+'_input');folder.mkdir()
        raw=trimesh.load(args.cases/case['source'],process=False)
        bits=json.loads((args.cases/case['labels']).read_text(encoding='utf-8'))['operand_bits']
        clean,labels,cleanup=clean_for_backend(raw,bits,'candidate')
        source=folder/'clean_source.obj';save_obj_fp64(clean,source)
        label=folder/'clean_labels.json';save(label,dict(operand_bits=np.asarray(labels).tolist()))
        tool=folder/'tool.obj';tool.write_bytes((args.cases/case['tool']).read_bytes())
        valid,metrics=local_fp64_valid(clean)
        cases[case['id']]=(source,label,tool)
        preconditions[case['id']]=dict(valid=valid,metrics=metrics,cleanup=cleanup,
            raw_source_sha256=case['source_sha256'],actual_input_sha256={p.name:sha256(p) for p in (source,label,tool)})
    tasks=schedule(cases)
    record=dict(time_beijing=now(),status='running',published=False,rows=[],preconditions=preconditions,
        manifest_sha256=sha256(manifest_path),entry_sha256=sha256(Path(__file__)),seed=2026100504,schedule=tasks,
        scope='已见三源三轮交错四真实方法，同源同工具同标签；共享GPU不作性能证据')
    result_path=args.output/'01-三源三轮四方法同输入比较.json'
    save(result_path,record)
    engine=PairEngines(args.output,args.port)
    try:
        record['environment']=engine.setup();save(result_path,record)
        for case,round_id,method in tasks:
            source,labels,tool=cases[case]
            folder=args.output/(case+'_r'+str(round_id)+'_'+method)
            condition=preconditions[case]
            if not condition['valid'] or (method!='boolean' and condition['metrics']['fp32_zero_area_faces']):
                row=dict(status='input_precondition_rejected',feature_method=method,input_metrics=condition['metrics'])
            else:
                row=engine.run(source,labels,tool,method,folder)
                row=engine.audit(source,tool,labels,folder,row)
            row.update(case=case,round=round_id,declared_method=method,artifact_directory=str(folder.resolve()),
                same_input_sha256={'source.obj':sha256(source),'labels.json':sha256(labels),'tool.obj':sha256(tool)})
            record['rows'].append(row);save(result_path,record)
            print(case,round_id,method,row['status'],flush=True)
        record.update(status='completed_with_recorded_outcomes',finished_beijing=now())
        save(result_path,record)
    finally:
        engine.close()
