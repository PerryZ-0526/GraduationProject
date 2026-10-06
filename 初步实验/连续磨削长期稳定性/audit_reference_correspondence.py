"""核对已保存参照的顶点双向对应、面连接及浮点舍入差异。"""
import argparse
from collections import Counter
from pathlib import Path
import sys
import numpy as np
from scipy.spatial import cKDTree
import trimesh
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '连续磨削实验基座'))
from event_store import atomic_json, digest, now, read_json


def oriented_faces(faces):
    # 仅允许面起点轮换，不将方向相反的三角形视作同一个有向面。
    return Counter(min(tuple(face), tuple(np.roll(face, 1)), tuple(np.roll(face, 2))) for face in faces)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--comparison', type=Path, required=True)
    args = parser.parse_args()
    original = read_json(args.comparison / '02-增量与完整前缀参照对照.json')
    identities = []
    with (args.folder / '02-事件索引.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            item = __import__('json').loads(line)
            if item['route'] == original['route'] and item['event'] == original['event']:
                record_path = args.folder / item['record_file']
                if digest(record_path) != item['record_sha256']:
                    raise ValueError('原事件记录摘要变化')
                identities.append(read_json(record_path)['state']['reference']['mesh'])
    if len(identities) != 1:
        raise ValueError('参照事件不唯一')
    incremental = Path(identities[0]['path'])
    replay = args.comparison / 'full_prefix' / 'validated_reference.obj'
    if digest(incremental) != original['incremental_sha256'] or digest(replay) != original['full_replay_sha256']:
        raise ValueError('对照保存参照摘要变化')
    left, right = trimesh.load(incremental, process=False), trimesh.load(replay, process=False)
    distance, mapping = cKDTree(right.vertices).query(left.vertices)
    reverse, backward = cKDTree(left.vertices).query(right.vertices)
    bijective = len(left.vertices) == len(right.vertices) and len(set(mapping)) == len(left.vertices) and len(set(backward)) == len(right.vertices)
    consistent = bijective and np.array_equal(backward[mapping], np.arange(len(left.vertices)))
    same_faces = consistent and oriented_faces(mapping[left.faces]) == oriented_faces(right.faces)
    spacing = float(np.max(np.spacing(np.abs(np.vstack((left.vertices, right.vertices))))))
    maximum = max(float(distance.max()), float(reverse.max()))
    result = {'time_beijing': now(), 'original_comparison_sha256': digest(args.comparison / '02-增量与完整前缀参照对照.json'),
        'byte_identical': original['byte_identical'], 'bidirectional_vertex_bijection': bool(consistent),
        'same_oriented_triangle_incidence': bool(same_faces), 'max_corresponding_vertex_distance_mm': maximum,
        'largest_coordinate_fp64_spacing_mm': spacing, 'difference_within_one_largest_coordinate_ulp': maximum <= spacing,
        'vertices': [len(left.vertices), len(right.vertices)], 'faces': [len(left.faces), len(right.faces)],
        'interpretation': '在本次有限前缀，同有向连接关系且对应坐标差处于一ULP量级；原字节不一致记录保留',
        'scope': '这是框架执行等价性控制，不是反馈距离停止规则、连续距离界或任意输入证明'}
    atomic_json(args.comparison / '03-排列与浮点差异核查.json', result)
    print(__import__('json').dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
