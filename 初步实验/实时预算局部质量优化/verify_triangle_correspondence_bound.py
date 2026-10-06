"""核对投影覆盖距离证书控制及全部实际保存的两模式输出。"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import numpy as np
from triangle_correspondence_bound import certify_correspondence, certify_with_virtual_snap


def control_checks():
    vertices = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
    old = np.array([[0, 1, 2], [0, 2, 3]])
    new = np.array([[0, 1, 3], [1, 2, 3]])
    bits = np.ones(2, dtype=np.uint8)
    controls = []
    for name, height, expected in [('完全共面', 0., True), ('微小离面', 1e-12, True), ('明确超界', 1e-3, False)]:
        v = vertices.copy()
        v[3, 2] = height
        result = certify_correspondence(v, old, bits, v, new, bits)
        assert result['accepted'] == expected
        controls.append(dict(name=name, result=result))
    for name, faces, labels in [('反向新面', new[:, ::-1], bits), ('来源被更改', new, np.array([1, 2])),
                                ('遗漏新面', new[:1], bits[:1]), ('重复新增面', np.vstack([new, new[:1]]), np.ones(3))]:
        result = certify_correspondence(vertices, old, bits, vertices, faces, labels)
        assert not result['accepted']
        controls.append(dict(name=name, result=result))
    # 虚拟坐标对应不修改任何真实输出；完整小分量的退化映像不能直接删除。
    changed = vertices.copy()
    changed[3, 2] = 1e-12
    result = certify_with_virtual_snap(vertices, old, bits, changed, new, bits)
    assert result['accepted'] and result.get('virtual_only') and result['error_upper_mm'] <= 1e-10
    controls.append(dict(name='新顶点微小编码差异辅助对应', result=result))
    tiny = np.array([[0., 0., 0.], [1e-12, 0., 0.], [0., 1e-12, 0.]])
    result = certify_with_virtual_snap(tiny, np.array([[0, 1, 2]]), bits[:1],
                                      tiny+np.array([0., 0., 1e-12]), np.array([[0, 1, 2]]), bits[:1])
    assert not result['accepted']
    controls.append(dict(name='完整小分量辅助删除拒绝', result=result))
    return controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    controls = control_checks()
    record_path = args.source / '01-已认证双输入候选同源完整对拍.json'
    source = json.loads(record_path.read_text())
    assert source['status'] in ('completed', 'completed_with_differences') and len(source['rows']) == source['cases'] == 27
    assert source['all_repeat_outputs_saved']
    rows = []
    for index, entry in enumerate(source['rows']):
        directory = args.source / f'case{index:02d}'
        for repeat in range(3):
            old_path = directory / f'repeat{repeat}_original.npz'
            new_path = directory / f'repeat{repeat}_certified.npz'
            a, b = np.load(old_path), np.load(new_path)
            result = certify_with_virtual_snap(a['vertices'], a['faces'], a['bits'], b['vertices'], b['faces'], b['bits'])
            rows.append(dict(name=entry['name'], repeat=repeat, result=result,
                             original_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest(),
                             candidate_sha256=hashlib.sha256(new_path.read_bytes()).hexdigest()))
    report = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(), status='completed',
                  source_status=source['status'], source_sha256=hashlib.sha256(record_path.read_bytes()).hexdigest(),
                  controls=controls, rows=rows, proved=sum(row['result']['accepted'] for row in rows), planned=81,
                  method_sha256={name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                 for name in [Path(__file__).name, 'triangle_correspondence_bound.py']},
                  scope='27例三轮全部实际保存对象几何对应；不替代嵌入、布尔真值或连续累计证书')
    assert not args.output.exists()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(dict(proved=report['proved'], planned=81,
                         unresolved=[row['name'] for row in rows if not row['result']['accepted']]), ensure_ascii=False))


if __name__ == '__main__':
    main()
