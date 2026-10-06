"""薄壁首刀最低SDF分辨率256完整输出的同源整面维护复审。"""

import getpass
import hashlib
import json
import os
from pathlib import Path
import sys


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    project = Path.cwd()
    snapshot = project / '初步实验/Geogram与PaMO切削排斥冻结_20261005_质量优先板体三刀真实反馈'
    manifest = snapshot / '01-执行源码冻结清单.json'
    for item in json.loads(manifest.read_text('utf8')):
        if sha(snapshot / item['file']) != item['sha256']:
            raise ValueError('固定数值依赖改变')
    sys.path.insert(0, str(snapshot))
    import numpy as np
    import trimesh
    from quality_ranked_exclusion import quality_ranked_exclusion
    from cut_side_classifier import ExactCutSide
    from cut_exclusion import supporting_planes, certify_face_support
    from exact_embedding_gate import mesh_valid_full_embedding
    from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution
    from audit_followup_candidate import quality_distribution
    from audit_cut_delivery import probes
    from locality_masks import save_obj_fp64
    from run_constrained_batch import RemoteQuality
    from run_geometry_study import execute, save, now
    evidence = Path('D:/GraduationProject_切削排斥证据')
    raw_batch = evidence / '20261005_薄壁最低分辨率256完整GPU'
    # 复用GPU模板留下旧文件名，实际首刀范围由物理输入SHA和目录绑定。
    raw_record = json.loads((raw_batch / '01-固定第二刀完整三阶段终态.json').read_text('utf8'))
    raw_path = raw_batch / raw_record['output']
    old = evidence / '20261005_固定原点六家族18事件完整开发/薄壁_新参数1p4375_交叉'
    stem = '薄壁_新参数1p4375_交叉_e0'
    source_path = old / (stem + '_candidate_input/clean_source.obj')
    labels_path = source_path.with_name('clean_labels.json')
    reference_path = old / (stem + '_reference/validated_reference.obj')
    if sha(raw_path) != raw_record['output_sha256'] or sha(source_path) != raw_record['source_sha256']:
        raise ValueError('固定新输出与物理源摘要不一致')
    prepared = evidence / '可复用磨削测试集/两档切削排斥新参数七家族_v28'
    pm = json.loads((prepared / '01-完整范围冻结清单.json').read_text('utf8'))
    route = next(r for r in pm['routes'] if r['id'] == '薄壁_新参数1p4375_交叉')
    tools = []
    tool_bindings = []
    for event in route['cutting_prefix_ids'][:1]:
        item = next(t for t in route['prefix_tools'] if t['event_id'] == event)
        path = prepared / 'inputs' / item['mesh']
        if sha(path) != item['sha256']:
            raise ValueError('累计工具摘要变化')
        tools.append(trimesh.load(path, force='mesh', process=False))
        tool_bindings.append({'event': event, 'sha256': sha(path)})
    output = evidence / '20261005_薄壁首刀最低分辨率256整面维护复审'
    output.mkdir(exist_ok=False)
    report = {'生成时间': now(), '修改时间及修改内容': '首次生成，固定新GPU输出单例维护',
              '文档概述': '同源开发，不含第二刀父反馈，不更改旧三事件分母', '索引目录': ['bindings', 'maintenance', 'audit'],
              'status': 'running', 'new_GPU_calls': 0, 'new_parent_feedback': False,
              'bindings': {'raw_sha256': sha(raw_path), 'source_sha256': sha(source_path), 'labels_sha256': sha(labels_path),
                           'reference_sha256': sha(reference_path), 'tools': tool_bindings, 'snapshot_sha256': sha(manifest)}}
    record = output / '01-首刀整面维护与保存复审.json'
    save(record, report)
    cfg = dict(line.split('=', 1) for line in (project / '.env').read_text('utf8').splitlines() if line and not line.startswith('#'))
    prompt = getpass.getpass
    os.environ['GPU_SSH_HOST'] = 'connect.westb.seetacloud.com'
    try:
        getpass.getpass = lambda _: cfg['CUDA_SSH_PASSWORD']
        engine = RemoteQuality(output, 51667)
    finally:
        getpass.getpass = prompt
        del cfg
    try:
        if execute(engine.client, ['mkdir', engine.remote])['returncode']:
            raise ValueError('隔离审计目录创建失败')
        validation = json.loads((project / '初步实验/Geogram与PaMO组合验证/实验结果/20261004_切削排斥精确材料侧分类开发/01-精确侧分类器与骨面锚点验证.json').read_text('utf8'))
        executable = validation['environment']['executable']
        if execute(engine.client, ['sha256sum', executable])['stdout'].split()[0] != validation['environment']['executable_sha256']:
            raise ValueError('精确材料侧分类器改变')
        side = ExactCutSide(engine, executable)
        source = trimesh.load(source_path, force='mesh', process=False)
        raw = trimesh.load(raw_path, force='mesh', process=False)
        reference = trimesh.load(reference_path, force='mesh', process=True, validate=True)
        bits = json.loads(labels_path.read_text('utf8'))['operand_bits']
        mesh, details = quality_ranked_exclusion(raw, tools, reference, source, bits, side.anchor)
        report['maintenance'] = details
        report['raw_quality'] = quality_distribution(raw)
        report['raw_probes'] = probes(raw, tools)
        if details['accepted']:
            # 保存后重新加载，再用冻结整面支撑与新的精确材料侧分类核对。
            saved = output / '02-首刀整面维护候选.obj'
            save_obj_fp64(mesh, saved)
            loaded = trimesh.load(saved, force='mesh', process=False)
            planes = [supporting_planes(tool) for tool in tools]
            normals, offsets = np.concatenate([p[0] for p in planes]), np.concatenate([p[1] for p in planes])
            selected = details['proposal_generator']['attempts'][details['selected_original_attempt_index']]['exclusion']
            certificates = [certify_face_support(loaded, normals, offsets, choice) for choice in selected['frozen_face_support_ids']]
            anchors = [side.anchor(loaded, tool, n, b) for tool, (n, b) in zip(tools, planes)]
            valid, metrics = mesh_valid_full_embedding(loaded, anchors[0]['classification'])
            topology = loaded.euler_number == source.euler_number and len(loaded.split(only_watertight=False)) == len(source.split(only_watertight=False))
            report['audit'] = {'passed': bool(valid and topology and all(r['passed'] for r in certificates + anchors)),
                               'saved_sha256': sha(saved), 'face_certificates': certificates, 'anchors': anchors,
                               'metrics': metrics, 'same_topology': topology, 'quality': quality_distribution(loaded),
                               'cumulative_distribution': geometry_error_distribution(loaded, reference),
                               'cut_distribution': cutting_surface_distribution(loaded, source, bits), 'probes': probes(loaded, tools)}
        report.update(status='completed', finished_beijing=now())
        save(record, report)
        print(json.dumps({'maintenance_accepted': details['accepted'], 'audit_passed': report.get('audit', {}).get('passed', False)}, ensure_ascii=False), flush=True)
    finally:
        engine.close()


if __name__ == '__main__':
    main()
