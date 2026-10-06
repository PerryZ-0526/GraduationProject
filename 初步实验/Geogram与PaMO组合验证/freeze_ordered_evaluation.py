"""开发终态后封存当前方法和全部保留输入，禁止提前以运行中记录释放评价。"""
import argparse
import ast
import json
from pathlib import Path
import re
from audit_followup_candidate import sha256
from run_geometry_study import now, save


def runtime_source_path(root, name):
    """只解析项目组合目录及已有共同运动审计目录，不搜索不相关实验副本。"""
    local=root/name
    if local.is_file():
        return local
    return root.parent/'共同运动记录与方法对照'/name


def runtime_sources(root, seeds):
    """封存入口的本地导入和显式源码文件依赖，生成副本另列而不覆盖生成器。"""
    pending=list(seeds);found=set()
    while pending:
        name=pending.pop()
        path=runtime_source_path(root,name)
        if name in found or not path.is_file():
            continue
        found.add(name)
        if path.suffix!='.py':
            continue
        source=path.read_text(encoding='utf-8')
        tree=ast.parse(source)
        for node in ast.walk(tree):
            modules=[]
            if isinstance(node,ast.Import):
                modules=[item.name for item in node.names]
            elif isinstance(node,ast.ImportFrom) and node.module:
                modules=[node.module]
            pending.extend(module.split('.')[0]+'.py' for module in modules)
        pending.extend(re.findall(r'[\"\']([A-Za-z_]\w*\.(?:py|cpp))[\"\']',source))
    return sorted(found)


def observed_candidate_parameters(record):
    """从实际工作器尝试读取区域生成参数，不把继承的CGAL标签当作共面预算。"""
    unique={}
    fields=('triangle_options','max_regions','max_added_per_region','plane_tolerance_mm','minimum_generated_face_area_mm2')
    for row in record.get('rows',[]):
        for attempt in row.get('attempts',[]):
            if not attempt.get('method','').startswith(('planar_','expanded_planar_')):
                continue
            observed={key:attempt[key] for key in fields if key in attempt}
            if observed:
                item=dict(method=attempt['method'],parameters=observed)
                unique[json.dumps(item,sort_keys=True)]=item
    return list(unique.values())


def freeze(development, prepared, output):
    record_path=development/'01-反馈执行与独立审计.json'
    record=json.loads(record_path.read_text(encoding='utf-8'))
    if record['status']!='completed_with_recorded_failures':
        raise ValueError('开发批次尚未终态，不能释放保留评价')
    manifest_path=prepared/'01-完整范围冻结清单.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    routes=manifest['routes']
    if len(routes)!=12 or any(r['split']!='evaluation' or len(r['cutting_prefix_ids'])!=4 for r in routes):
        raise ValueError('保留评价必须包含原12路线48事件完整分母')
    inputs=[]
    for route in routes:
        for name,digest in [(route['initial_mesh'],route['initial_mesh_sha256']),
            *[(t['mesh'],t['sha256']) for t in route['prefix_tools']]]:
            path=(prepared/'inputs'/name).resolve()
            if not path.is_relative_to((prepared/'inputs').resolve()) or sha256(path)!=digest:
                raise ValueError('冻结输入变化或跨包引用')
            inputs.append(dict(file=name,sha256=digest))
    if len(inputs)!=60 or len({r['file'] for r in inputs})!=60:
        raise ValueError('保留输入60对象存在缺失或重用')
    required=('initial_encoding_worker.py','planar_patch.py','preserved_reference.py',
        'ordered_physical_cleanup.py','ordered_physical_cleanup_snapshot.py')
    if any(not (development/name).is_file() for name in required):
        raise ValueError('开发实际方法副本缺失')
    reference=(development/'preserved_reference.py').read_text(encoding='utf-8')
    if not all(marker in reference for marker in ('ordered_cancel_opposed as clean_cancel_opposed',
        'prefix_tools_through(route, event)', 'sha256(initial) != route["initial_mesh_sha256"]',
        'sha256(source) != tool["sha256"]')) or 'candidate.obj' in reference:
        raise ValueError('不是原初态工具数据独立的顺序修复参照')
    output.mkdir(exist_ok=False)
    sources=output/'方法副本';sources.mkdir()
    files=[]
    # 冻结实际执行目录中的源码，包括生成工作器；不以主仓文件替代实际版本。
    for path in sorted(p for p in development.iterdir() if p.suffix in ('.py','.cpp')):
        copied=sources/path.name;copied.write_bytes(path.read_bytes())
        files.append(dict(file=str(copied.relative_to(output)),sha256=sha256(copied)))
    runtime=output/'运行入口与依赖';runtime.mkdir()
    root=Path(__file__).resolve().parent
    entry=record['environment'].get('evaluation_entry_file','run_ordered_reference_feedback.py')
    if entry not in ('run_ordered_reference_feedback.py','run_active_patch_feedback.py'):
        raise ValueError('没有登记实际评价入口')
    seeds=[entry]+[Path(row['file']).name for row in files]
    dependencies=[]
    for name in runtime_sources(root,seeds):
        original=runtime_source_path(root,name)
        copied=runtime/name;copied.write_bytes(original.read_bytes())
        dependencies.append(dict(file=str(copied.relative_to(output)),sha256=sha256(copied),source_path=str(original.resolve())))
    result=dict(time_beijing=now(),development_record_sha256=sha256(record_path),
        development_status=record['status'],manifest_sha256=sha256(manifest_path),
        routes=[r['id'] for r in routes],planned_events=48,inputs=inputs,method_files=files,runtime_files=dependencies,
        observed_candidate_parameters=observed_candidate_parameters(record),
        actual_environment=record['environment'],execution_entry=entry,evaluation_results_opened=False,
        scope='实际开发终态副本及全部12路线48事件冻结；不证明评价结果或连续距离',
        policy='固定源码和预算；首次失败及受阻完整记录，评价不调参或剔除路线')
    save(output/'01-方法与保留评价完整冻结.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('development','prepared','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    result=freeze(args.development,args.prepared,args.output)
    print(len(result['routes']),result['planned_events'],len(result['inputs']),len(result['method_files']))
