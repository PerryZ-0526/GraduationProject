"""重加载同输入消融产物，分别核对前置拒绝与实际有效输出。"""
import argparse
import json
from pathlib import Path
import shlex
import numpy as np
import trimesh
from audit_followup_candidate import sha256
from audit_published_anchor_records import check_anchor_record
from initial_encoding_saved_contract import check_initial_encoding_record
from preserved_feedback_gate import local_fp64_valid
from run_constrained_feedback import global_geometry
from run_constrained_batch import RemoteQuality
from run_geometry_study import retrieve,save,now


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args()
    manifest_path=args.cases/'01-冻结清单.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    path=args.output/'01-冻结源初态规则交错消融.json'
    report=json.loads(path.read_text(encoding='utf-8'))
    if report['status'] != 'completed_with_recorded_outcomes' or report['manifest_sha256'] != sha256(manifest_path):
        raise ValueError('消融未终态或输入清单变化')
    cases={case['id']:case for case in manifest['cases']}
    result=dict(time_beijing=now(),record_sha256=sha256(path),rows=[],published=False,
        scope='实际保存网格、前置拒绝NPZ、固定坐标及同摘要全量嵌入证据；非连续误差证书')
    remote=RemoteQuality(args.output,args.port)
    try:
        for row in report['rows']:
            folder=Path(row['artifact_directory']);case=cases[row['case']]
            source=trimesh.load(args.cases/case['source'],process=False)
            before_name='before_precondition.obj' if row['variant']=='without_initial_anchors' else 'before_projection.obj'
            before_path=folder/before_name;before=trimesh.load(before_path,process=False)
            item=dict(case=row['case'],round=row['round'],variant=row['variant'],status=row['status'])
            before_ok=sha256(before_path)==row['before_sha256']
            if row['status']=='execution_failed':
                command=shlex.split(row['execution']['command']);remote_output=command[command.index('--output')+1]
                npz=folder/'precondition.npz';retrieve(remote.client,remote.sftp,remote_output+'/precondition.npz',npz)
                data=np.load(npz)
                encoded=(data['vertices']*data['scale']+data['translation']).astype(np.float32).astype(float)
                tri=encoded[data['faces']]
                area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)*.5
                unsupported=(area <= 1e-12*data['scale']**2)&~data['fixed'][data['faces']].all(axis=1)
                exact=np.array_equal(data['vertices'],before.vertices) and np.array_equal(data['faces'],before.faces)
                reason='GPU编码退化面仍含自由顶点' in (folder/'worker.log').read_text(encoding='utf-8')
                passed=before_ok and exact and reason and bool(unsupported.any()) and local_fp64_valid(before)[0]
                item.update(unsupported_encoded_faces=int(unsupported.sum()),npz_matches_before=exact,
                    negative_artifact_check_passed=bool(passed),npz_sha256=sha256(npz))
            else:
                candidate_path=folder/'candidate.obj';mesh=trimesh.load(candidate_path,process=False)
                valid,metrics=local_fp64_valid(mesh);geometry=global_geometry(mesh,source)
                ids=np.asarray(row['vertex_original_ids']);original=ids>=0
                fixed=np.array_equal(mesh.vertices[original],source.vertices[ids[original]])
                anchors=row.get('anchor_updates')
                anchor_ok=row.get('projection')=='no_free_vertices_identity' if anchors is None else (
                    json.loads((folder/'anchor_updates.json').read_text(encoding='utf-8'))==anchors and check_anchor_record(anchors,ids))
                if anchors:
                    anchor_ok=anchor_ok and all(np.array_equal(mesh.vertices[u['added_vertices']],before.vertices[u['added_vertices']]) for u in anchors['updates'])
                certificate=row['output_metrics']['full_exact_embedding']
                embedding=certificate.get('embedded_closed') and certificate.get('saved_sha256')==sha256(candidate_path)
                initial=True
                if row['variant']=='with_initial_anchors':
                    contract=check_initial_encoding_record(source.vertices,before.vertices,before.faces,mesh.vertices,ids,row['initial_encoding_anchors'])
                    initial=contract['passed'];item['initial_encoding_contract']=contract
                passed=bool(before_ok and row['status']=='accepted_sampled' and valid and embedding and fixed and anchor_ok and initial
                    and sha256(candidate_path)==row['output_sha256'] and np.array_equal(mesh.faces,before.faces)
                    and mesh.euler_number==source.euler_number and geometry['probe_max_mm']<=.1 and row['numerical_diagnostic']['passed'])
                item.update(saved_output_check_passed=passed,source_geometry=geometry,local_metrics=metrics,
                    full_embedding_bound=bool(embedding),original_fixed_exact=bool(fixed),added_anchors_exact=bool(anchor_ok))
            item['passed']=bool(passed);result['rows'].append(item)
        result.update(artifacts=len(result['rows']),passed=sum(row['passed'] for row in result['rows']),
            accepted_outputs=sum(row['status']=='accepted_sampled' for row in result['rows']))
        save(args.output/'02-冻结源消融实际保存对象复审.json',result)
        print(result['passed'],'/',result['artifacts'],'accepted outputs',result['accepted_outputs'])
        if result['passed']!=result['artifacts']:raise SystemExit(1)
    finally:
        remote.close()
