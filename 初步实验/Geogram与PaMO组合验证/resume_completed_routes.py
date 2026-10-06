"""仅在环境中断发生于完整路线边界时继续原批次，保留全部既有分母。"""
import argparse
from functools import partial
import json
from pathlib import Path
from recheck_completed_preserved_route import require_complete_route
from run_initial_encoding_feedback import InitialPhysicalEngine
from run_preserved_geometry_feedback import load_snapshot, EXPECTED_CHECKER
from preserved_controller_source import replace_once
from physical_feedback_gate import clean_for_backend
from preserved_feedback_gate import check_preserved_mesh, audit_preserved_candidate
from locality_diagnostic import source_region, verify_labels
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER


def completed_routes(report, manifest, output):
    if report['manifest_sha256'] != sha256(output/'input_manifest.json'):
        raise ValueError('恢复清单摘要不符')
    completed = []
    for route in manifest['routes']:
        rows = [r for r in report['rows'] if r['route'] == route['id']]
        if not rows:
            if any(output.glob(route['id']+'_*')):
                raise ValueError('未登记路线已有产物，不能自动从初态继续')
            continue
        require_complete_route(report, route)
        if route['id'] not in report.get('route_event_policy', {}):
            raise ValueError('路线结束状态未落盘')
        for row in rows:
            if row['status'] == 'published_under_sampled_and_vertex_protocol':
                path = output/(route['id']+'_'+row['event']+'_'+row['branch']+'_'+row['selected_method'])/'candidate.obj'
                if sha256(path) != row['output_sha256']:
                    raise ValueError('恢复发布对象摘要不符')
        completed.append(route['id'])
    return completed


class ResumeEngine(InitialPhysicalEngine):
    def setup(self):
        info = json.loads((self.output/'02-本批方法冻结.json').read_text(encoding='utf-8'))['environment']
        running=execute(self.client,['pgrep','-af','run_constrained_worker.py'])
        if any(self.remote+'/' in line for line in running['stdout'].splitlines()):
            raise ValueError('原批次仍有GPU工作器，不能并行恢复')
        # 复用同目录已完成编译和实际工作器，不重新生成或覆盖旧机制。
        for remote_name, expected in [('run_constrained_worker.py',info['actual_initial_encoding_worker_sha256']),
            ('constrained_remesh',info['executable_sha256']), (CHECKER,EXPECTED_CHECKER)]:
            remote = remote_name if remote_name.startswith('/') else self.remote+'/'+remote_name
            if execute(self.client, ['sha256sum',remote])['stdout'].split()[0] != expected:
                raise ValueError('恢复远端机制摘要变化：'+remote_name)
        for name, expected in info['initial_encoding_feedback_source_sha256'].items():
            from run_constrained_batch import HERE
            if sha256(HERE/name) != expected or sha256(self.output/name) != expected:
                raise ValueError('恢复本机机制摘要变化：'+name)
        return info


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--split',required=True)
    args=parser.parse_args()
    manifest_path=args.prepared/'01-完整范围冻结清单.json'
    frozen=args.output/'input_manifest.json'
    if not frozen.exists():
        frozen.write_bytes(manifest_path.read_bytes())
    if sha256(frozen) != sha256(manifest_path):
        raise ValueError('原输入清单变化')
    report=json.loads((args.output/'01-反馈执行与独立审计.json').read_text(encoding='utf-8'))
    done=completed_routes(report,json.loads(frozen.read_text(encoding='utf-8')),args.output)
    source=(args.output/'preserved_controller.py').read_text(encoding='utf-8')
    source=replace_once(source,'    if args.output.exists():\n        raise FileExistsError(args.output)\n','')
    source=replace_once(source,'    args.output.mkdir(parents=True)','    args.output.mkdir(parents=True, exist_ok=True)')
    source=replace_once(source,'    engine = RemoteQuality(args.output, args.port)',
        '    report = RESUME_REPORT\n    report["status"] = "running"\n    engine = RemoteQuality(args.output, args.port)')
    source=replace_once(source,'        for route in routes:\n            rid = route["id"]',
        '        for route in routes:\n            if route["id"] in RESUME_COMPLETED:\n                continue\n            rid = route["id"]')
    # 冻结恢复控制器及IO版本；原算法、完整清单和已完成路线不重跑。
    path=args.output/'resume_completed_controller.py';path.write_text(source,encoding='utf-8')
    controller=load_snapshot('resume_completed_controller',path)
    reference=load_snapshot('resume_completed_reference',args.output/'preserved_reference.py')
    report.setdefault('resumptions',[]).append(dict(time_beijing=now(),completed_routes=done,
        controller_sha256=sha256(path), entry_sha256=sha256(Path(__file__))))
    controller.RESUME_REPORT=report;controller.RESUME_COMPLETED=set(done)
    engine=ResumeEngine(args.output,args.port)
    controller.RemoteQuality=lambda output,port:engine
    def recover(engine, prepared, route, event, initial_remote, folder, reuse):
        mesh, record=reference.recover_reference(engine,prepared,route,event,initial_remote,folder,reuse)
        if mesh is not None:
            # 保留原入口在逐步参照之后的最终完整几何核查。
            valid, metrics=check_preserved_mesh(engine,Path(folder)/'full_geometry_checks',mesh,'recovered_reference')
            record['validated_metrics']=metrics;record['accepted']=valid
            if not valid:
                return None,record
        return mesh,record
    controller.REFERENCE_RECOVERY=recover
    controller.VALID_SOURCE_BITS=(1,2,3)
    controller.source_region=partial(source_region,allow_shared=True)
    controller.verify_labels=partial(verify_labels,allow_shared=True)
    controller.audit_candidate=lambda *values:audit_preserved_candidate(engine,*values)
    controller.clean_for_backend=clean_for_backend
    controller.main()
