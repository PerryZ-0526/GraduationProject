"""两条解析长路线完整前缀的等值面补查，不改已发布状态或作为连续真值。"""
import argparse
import json
from pathlib import Path
import trimesh
from audit_followup_candidate import sha256
from generate_followup_reference import reference_mesh
from recheck_completed_preserved_route import require_complete_route
from run_constrained_feedback import global_geometry
from run_geometry_study import now,save


def validate(prepared,run):
    manifest_path=prepared/'01-完整范围冻结清单.json';record_path=run/'01-反馈执行与独立审计.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'));record=json.loads(record_path.read_text(encoding='utf-8'))
    if record['status']!='completed_with_recorded_failures' or record['split']!='long' or sha256(manifest_path)!=record['manifest_sha256']:
        raise ValueError('必须为同清单的完整长路线终态')
    routes=[r for r in manifest['routes'] if r['split']=='long']
    if len(routes)!=2 or sum(len(r['cutting_prefix_ids']) for r in routes)!=48:
        raise ValueError('两条24步完整分母不符')
    for route in routes:
        require_complete_route(record,route)
        if not route.get('analytic_body') or route['body']=='ct':
            raise ValueError('缺少解析体身份，不能凭合成标签猜数学表面')
        if sha256(prepared/'inputs'/route['initial_mesh'])!=route['initial_mesh_sha256']:
            raise ValueError('原始初态摘要变化')
        for tool in route['prefix_tools']:
            if sha256(prepared/'inputs'/tool['mesh'])!=tool['sha256']:
                raise ValueError('原物理工具摘要变化')
    return routes,record,manifest_path,record_path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('prepared','run','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    routes,record,manifest_path,record_path=validate(args.prepared,args.run)
    args.output.mkdir(exist_ok=False)
    root=Path(__file__).resolve().parent
    code={}
    for name in ('audit_analytic_long_reference.py','generate_followup_reference.py','followup_reference.py'):
        path=args.output/name;path.write_bytes((root/name).read_bytes());code[name]=sha256(path)
    report=dict(time_beijing=now(),status='running',rows=[],planned_prefixes=48,spacing_mm=.025,
        manifest_sha256=sha256(manifest_path),maintenance_record_sha256=sha256(record_path),code_sha256=code,
        scope='原解析体与实际轨迹的独立规则等值面补查；解析球工具与离散工具存在离散差异，网格间探针不是连续距离上界；不改原发布状态、不改独立评价算法')
    path=args.output/'01-两条长路线48前缀解析等值面补查.json'
    save(path,report)
    for route in routes:
        for event in route['cutting_prefix_ids']:
            folder=args.output/(route['id']+'_'+event);folder.mkdir()
            # 参照生成只读取原解析体和冻结事件，不读取候选或其父网格。
            surface,diagnostics=reference_mesh(route,event,.025)
            reference=folder/'analytic_reference.vtp';surface.save(reference)
            row=dict(route=route['id'],event=event,reference_sha256=sha256(reference),diagnostics=diagnostics,branches={})
            for branch in ('full','candidate'):
                original=next(r for r in record['rows'] if (r['route'],r['event'],r['branch'])==(route['id'],event,branch))
                item=dict(original_status=original['status'])
                if original['status']=='published_under_sampled_and_vertex_protocol':
                    candidate=args.run/(route['id']+'_'+event+'_'+branch+'_'+original['selected_method'])/'candidate.obj'
                    if sha256(candidate)!=original['output_sha256']:
                        raise ValueError('实际发布对象摘要变化')
                    geometry=global_geometry(trimesh.load(candidate,process=False),surface)
                    item.update(output_sha256=sha256(candidate),geometry=geometry,
                        within_point_probe_0_1_mm=geometry['probe_max_mm']<=.1)
                row['branches'][branch]=item
            report['rows'].append(row);save(path,report)
            print(route['id'],event,'解析等值面补查完成',flush=True)
    report.update(status='completed_with_recorded_outcomes',finished_beijing=now());save(path,report)
