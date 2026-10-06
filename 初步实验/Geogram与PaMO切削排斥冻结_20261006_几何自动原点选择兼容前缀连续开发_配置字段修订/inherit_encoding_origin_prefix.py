"""显式继承同源兼容的三次发布及一次完整控制，不重复GPU，不混入新计数。"""
import json
from pathlib import Path
import shutil
from audit_followup_candidate import sha256


def inherit_origin_prefix(args, report, route):
    prefix = args.inherited_prefix
    proof_path = prefix / '02-兼容继承资格与证据绑定.json'
    proof = json.loads(proof_path.read_text('utf8'))
    old_path = Path(proof['base_snapshot']) / '01-执行源码冻结清单.json'
    if sha256(old_path) != proof['base_snapshot_sha256']:
        raise ValueError('原方法冻结绑定改变')
    # 新入口只新增表示选择与继承，其他数值算法必须逐文件保持原冻结摘要。
    for item in json.loads(old_path.read_text('utf8')):
        if item['file'] == 'run_reference_budget_feedback.py':
            continue
        if sha256(Path(__file__).parent / item['file']) != item['sha256']:
            raise ValueError('继承时其他数值模块改变：' + item['file'])
    if sha256(Path(__file__).with_name('geometry_selected_encoding_origin.py')) != proof['selector_sha256']:
        raise ValueError('表示选择与资格验证不是同一个规则')
    original_path = prefix / '01-统一配置完整父反馈记录.json'
    if sha256(original_path) != proof['prefix_record_sha256']:
        raise ValueError('继承结果记录摘要不符')
    original = json.loads(original_path.read_text('utf8'))
    qa_path = Path(proof['saved_audit_path'])
    if sha256(qa_path) != proof['saved_audit_sha256']:
        raise ValueError('继承保存对象复审改变')
    qa = json.loads(qa_path.read_text('utf8'))
    if qa['status'] != 'completed' or qa['summary']['passed'] != 4 or not all(r['passed'] for r in qa['rows']):
        raise ValueError('四份继承保存对象没有全部通过独立复审')
    if original['manifest_sha256'] != report['manifest_sha256'] or original['reference_batch_sha256'] != report['reference_batch_sha256']:
        raise ValueError('继承初态、工具或独立参照绑定改变')
    rid = route['id']
    parent_hash = route['initial_mesh_sha256']
    if [r['event'] for r in original['rows']] != route['cutting_prefix_ids'][:4]:
        raise ValueError('兼容前缀不是原计划前四事件')
    for index, row in enumerate(original['rows']):
        event = row['event']
        if row['status'] != 'published_geometry_observation' or row['parent_sha256'] != parent_hash:
            raise ValueError('继承状态或真实父链不匹配')
        selected = proof['origin_controls'][index]
        if selected['event'] != event or not selected['encoded_vertices_faces_bitwise_same'] or not selected['source_vertices_faces_bitwise_unchanged']:
            raise ValueError('继承没有同源实际GPU表示逐位证据')
        stage = row['actual_stage3_representation']
        if stage['status'] != 'completed_original_solver' or stage['diff_calls'] != 50 or stage['ccd_calls'] != 50 or stage['author_do_nothing']:
            raise ValueError('继承没有完整原求解证据')
        for suffix in ['candidate_input', 'reference', 'candidate_boolean']:
            folder_name = rid + '_' + event + '_' + suffix
            shutil.copytree(prefix / folder_name, args.output / folder_name)
        source = args.output / (rid + '_' + event + '_candidate_input/clean_source.obj')
        labels = source.with_name('clean_labels.json')
        output = args.output / (rid + '_' + event + '_candidate_boolean/candidate.obj')
        reference = args.output / (rid + '_' + event + '_reference/validated_reference.obj')
        if sha256(source) != row['attempt']['inputs_sha256']['source.obj'] or sha256(labels) != row['attempt']['inputs_sha256']['labels.json']:
            raise ValueError('继承实际源或标签摘要不符')
        if sha256(output) != row['output_sha256'] or sha256(reference) != row['reference_sha256']:
            raise ValueError('继承输出或独立参照摘要不符')
        row['execution_role'] = 'inherited_prior_publication' if index < 3 else 'adopted_verified_same_source_control'
        row['GPU_calls_in_this_continuation'] = 0
        report['rows'].append(row)
        parent_hash = row['output_sha256']
    report['inherited_prefix'] = {'events': 4, 'prior_publications': 3, 'adopted_same_source_controls': 1,
                                  'new_GPU_calls': 0, 'proof_sha256': sha256(proof_path),
                                  'saved_audit_sha256': proof['saved_audit_sha256'],
                                  'single_version_from_initial_run': False}
    return args.output / (rid + '_' + original['rows'][-1]['event'] + '_candidate_boolean/candidate.obj')
