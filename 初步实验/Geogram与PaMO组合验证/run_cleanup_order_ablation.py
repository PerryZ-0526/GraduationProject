"""同输入四因素清理对照，区分修复顺序与编码退化检查位置。"""
import argparse
import json
from pathlib import Path
import random
import numpy as np
import trimesh
from audit_followup_candidate import sha256
from locality_masks import save_obj_fp64
from ordered_physical_cleanup import SOURCE
from preserved_controller_source import replace_once
from preserved_feedback_gate import local_fp64_valid
from run_geometry_study import now, save


def variants():
    """只改变两个已声明因素，旧函数、固定预算和联合门槛均保留。"""
    original = Path(__file__).with_name('opposed_facet_cleanup.py').read_text(encoding='utf-8')
    return {
        'original': original,
        'repair_before_guard': replace_once(SOURCE, 'if not valid or not topology:',
            'if not valid or metrics["fp32_zero_area_faces"] or not topology:'),
        'defer_encoding_guard': replace_once(original,
            'if not valid or metrics["fp32_zero_area_faces"] or not topology:', 'if not valid or not topology:'),
        'repair_and_defer': SOURCE,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = args.cases/'01-清理顺序回归资产清单.json'
    package = json.loads(manifest.read_text(encoding='utf-8'))
    for item in package['files']:
        path = (args.cases/item['file']).resolve()
        if not path.is_relative_to(args.cases.resolve()) or sha256(path) != item['sha256']:
            raise ValueError('消融冻结输入变化或跨包引用')
    args.output.mkdir(exist_ok=False)
    mesh = trimesh.load(args.cases/'inputs/source.obj', process=False)
    bits = np.asarray(json.loads((args.cases/'inputs/labels.json').read_text(encoding='utf-8'))['operand_bits'])
    methods = {}
    sources = {}
    for name, source in variants().items():
        path = args.output/(name+'_snapshot.py')
        path.write_text(source, encoding='utf-8')
        namespace = dict(__name__=name+'_snapshot')
        exec(compile(source, str(path), 'exec'), namespace)
        methods[name] = namespace['clean_cancel_opposed']
        sources[name] = sha256(path)
    schedule = [(round_id, name) for round_id in range(3) for name in methods]
    random.Random(2026100502).shuffle(schedule)
    record = dict(time_beijing=now(), status='running', published=False, rows=[],
        manifest_sha256=sha256(manifest), entry_sha256=sha256(Path(__file__)),
        source_sha256=sources, seed=2026100502, schedule=schedule,
        scope='已见CT同源三轮交错四因素清理；本地候选不代表精确嵌入、GPU数值或发布')
    output = args.output/'01-同输入清理因素交错对照.json'
    save(output, record)
    for round_id, name in schedule:
        row = dict(round=round_id, variant=name, input_sha256=sha256(args.cases/'inputs/source.obj'))
        try:
            candidate, labels, details = methods[name](mesh.copy(), bits.copy(), allow_shared=True)
            valid, metrics = local_fp64_valid(candidate)
            path = args.output/(name+'_r'+str(round_id)+'.obj')
            save_obj_fp64(candidate, path)
            save(args.output/(name+'_r'+str(round_id)+'_labels.json'), dict(operand_bits=labels.tolist()))
            row.update(status='local_candidate' if valid else 'local_invalid', metrics=metrics,
                details=details, candidate_sha256=sha256(path), labels_count=len(labels), faces=len(candidate.faces))
        except ValueError as error:
            row.update(status='rejected', error=str(error))
        record['rows'].append(row)
        save(output, record)
        print(round_id, name, row['status'], flush=True)
    record.update(status='completed_with_recorded_outcomes', finished_beijing=now())
    save(output, record)
