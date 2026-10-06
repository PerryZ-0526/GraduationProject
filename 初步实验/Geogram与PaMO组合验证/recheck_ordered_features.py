"""按36条完整分母重加载小特征输出，保留真实失败与方法前提差异。"""
import argparse
import json
from pathlib import Path
import shlex
import numpy as np
import trimesh
from audit_followup_candidate import sha256
from audit_published_anchor_records import check_anchor_record
from constrained_quality import fixed_surface_contract
from initial_encoding_saved_contract import check_initial_encoding_record
from locality_masks import make_masks
from preserved_saved_binding import collect_certificates, mesh_valid_saved_binding
from run_constrained_batch import RemoteQuality
from run_constrained_feedback import global_geometry
from run_geometry_study import execute, retrieve, save, now


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prepared','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    args = parser.parse_args()
    manifest_path = args.prepared/'01-完整范围冻结清单.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    record_path = args.output/'02-浅磨特征保持审计.json'
    report = json.loads(record_path.read_text(encoding='utf-8'))
    if report['status'] != 'completed_with_recorded_failures' or report['manifest_sha256'] != sha256(manifest_path):
        raise ValueError('小特征批次尚未终态或输入清单变化')
    expected = {(item['id'],method) for item in manifest['negative_inputs'] for method in ('full','global','spatial','boolean')}
    actual = [(r['case'],r.get('feature_method',r.get('method'))) for r in report['rows']]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError('当前36条方法分母缺失或重复；源失败不得当作维护成功')
    tools = {r['id']:r for r in json.loads((args.output/'01-小特征浅磨工具冻结.json').read_text(encoding='utf-8'))['rows']}
    certificates = collect_certificates(report)
    remote = RemoteQuality(args.output,args.port)
    result = dict(time_beijing=now(),record_sha256=sha256(record_path),rows=[],published=False,
        scope='完整36条分母、同次上传输入、实际返回网格与拒绝证据重审；不证明连续误差或孔径数值界')
    try:
        for row in report['rows']:
            case,method = row['case'],row.get('feature_method',row.get('method'))
            source_path = args.output/(case+'_input')/'clean_source.obj'
            labels_path = source_path.with_name('clean_labels.json')
            tool_path = args.output/tools[case]['tool']
            inputs = {'source.obj':sha256(source_path),'labels.json':sha256(labels_path),'tool.obj':sha256(tool_path)}
            if inputs != row.get('inputs_sha256') or sha256(tool_path) != tools[case]['sha256']:
                raise ValueError('实际方法上传输入或工具摘要不一致')
            folder = args.output/(case+'_'+method)
            item = dict(case=case,method=method,recorded_status=row['status'],input_sha256=inputs)
            if row['execution']['returncode']:
                log = folder/'worker.log'
                # 失败只计同次日志和退出证据，不制造不存在的返回网格。
                passed = row['status']=='execution_failed' and log.is_file() and log.stat().st_size>0
                item.update(kind='execution_failure_evidence',worker_log_sha256=sha256(log),passed=bool(passed))
            else:
                output = folder/'candidate.obj'
                mesh = trimesh.load(output,process=False)
                source = trimesh.load(source_path,process=False)
                valid,metrics = mesh_valid_saved_binding(mesh,certificates)
                geometry = global_geometry(mesh,source)
                topology = mesh.euler_number==source.euler_number and len(mesh.split(only_watertight=False))==len(source.split(only_watertight=False))
                contract = True
                if method=='boolean':
                    command=shlex.split(row['execution']['command'])
                    remote_before=command[command.index('--output')+1]+'/before_projection.obj'
                    digest=execute(remote.client,['sha256sum',remote_before])['stdout'].split()[0]
                    before_path=folder/'before_projection.obj'
                    retrieve(remote.client,remote.sftp,remote_before,before_path)
                    before=trimesh.load(before_path,process=False)
                    ids=np.asarray(row['vertex_original_ids']);original=ids>=0
                    initial=check_initial_encoding_record(source.vertices,before.vertices,before.faces,mesh.vertices,ids,row['initial_encoding_anchors'])
                    anchors=row.get('anchor_updates')
                    added=row.get('projection')=='no_free_vertices_identity' if anchors is None else (
                        json.loads((folder/'anchor_updates.json').read_text(encoding='utf-8'))==anchors and check_anchor_record(anchors,ids)
                        and all(np.array_equal(mesh.vertices[u['added_vertices']],before.vertices[u['added_vertices']]) for u in anchors['updates']))
                    contract=bool(digest==sha256(before_path) and initial['passed'] and added
                        and np.array_equal(mesh.vertices[original],source.vertices[ids[original]]) and np.array_equal(mesh.faces,before.faces)
                        and row['numerical_diagnostic']['passed'])
                    item['initial_encoding_contract']=initial
                elif method!='full':
                    bits=json.loads(labels_path.read_text(encoding='utf-8'))['operand_bits']
                    active,fixed=make_masks(source,bits,trimesh.load(tool_path,process=False),method,2)
                    contract=fixed_surface_contract(source,mesh,active,fixed)['passed']
                accepted=bool(valid and topology and geometry['probe_max_mm']<=.1 and contract and not row.get('capacity_changed')
                    and (method=='boolean' or metrics['fp32_zero_area_faces']==0))
                decision_matches=(row['status']=='accepted_sampled')==accepted
                passed=bool(sha256(output)==row['output_sha256'] and decision_matches)
                item.update(kind='returned_output',passed=passed,recomputed_accepted=accepted,metrics=metrics,
                    geometry=geometry,topology_matches_source=bool(topology),fixed_contract_passed=bool(contract),
                    geometry_to_feature_width_ratio=geometry['probe_max_mm']/row['feature_width_mm'])
            result['rows'].append(item)
        result.update(artifacts=len(result['rows']),passed=sum(r['passed'] for r in result['rows']),
            returned_outputs=sum(r['kind']=='returned_output' for r in result['rows']),
            accepted_outputs=sum(r.get('recomputed_accepted',False) for r in result['rows']))
        save(args.output/'03-小特征完整分母与保存对象复审.json',result)
        print(result['passed'],'/',result['artifacts'],'returned',result['returned_outputs'],'accepted',result['accepted_outputs'])
        if result['passed']!=result['artifacts']:
            raise SystemExit(1)
    finally:
        remote.close()
