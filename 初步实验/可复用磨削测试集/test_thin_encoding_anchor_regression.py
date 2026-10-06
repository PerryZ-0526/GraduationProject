"""薄壁编码退化负例和新完整投影绑定冻结对象。"""
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent/'薄壁编码退化初态锚点回归_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ThinEncodingRegressionTests(unittest.TestCase):
    def test_frozen_files(self):
        items = read(ROOT/'01-冻结清单.json')['files']
        self.assertEqual(len(items), 20)
        for item in items:
            self.assertEqual(digest(ROOT/item['file']), item['sha256'])

    def test_physical_valid_encoded_failure(self):
        record = read(ROOT/'capture/boolean/02-物理面积与编码退化定位.json')
        self.assertEqual(record['physical_bad_faces'], 0)
        self.assertEqual(record['encoded_bad_faces'], 1)
        self.assertEqual(len(record['unsupported_free_vertices']), 1)
        self.assertFalse(record['published'])
        exact = read(ROOT/'capture/03-同保存对象全量嵌入审计.json')
        self.assertTrue(exact['passed'])
        self.assertEqual(exact['saved_sha256'], digest(ROOT/'capture/boolean/before_precondition.obj'))

    def test_full_projection_saved_objects(self):
        record = read(ROOT/'projection/01-初态编码锚点完整投影诊断.json')
        self.assertFalse(record['published'])
        self.assertEqual(record['status'], 'completed_with_recorded_outcomes')
        for method, row in zip(('boolean', 'expanded'), record['rows']):
            self.assertEqual(row['status'], 'accepted_sampled')
            self.assertEqual(row['numerical_diagnostic']['finite_energy_calls'], 50)
            self.assertTrue(row['numerical_diagnostic']['passed'])
            self.assertEqual(row['output_sha256'], digest(ROOT/'projection'/method/'candidate.obj'))
            self.assertTrue(row['output_metrics']['full_exact_embedding_bound'])

    def test_rule_matches_recorded_initial_encoding(self):
        data = np.load(ROOT/'capture/boolean/precondition.npz')
        vertices, faces = data['vertices'], data['faces']
        encoded = (vertices*data['scale']+data['translation']).astype(np.float32).astype(float)
        tri = encoded[faces]
        area = np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)*.5
        affected = np.unique(faces[area <= 1e-12*data['scale']**2])
        expected = affected[~data['fixed'][affected]].tolist()
        rows = read(ROOT/'projection/01-初态编码锚点完整投影诊断.json')['rows']
        for row in rows:
            self.assertEqual(row['initial_encoding_anchors']['added_vertices'], expected)
        # 逐位检查冻结输出，不把规则记录中的选点数量当作坐标保持证据。
        for method in ('boolean', 'expanded'):
            output = trimesh.load(ROOT/'projection'/method/'candidate.obj', process=False)
            np.testing.assert_array_equal(output.vertices[affected], vertices[affected])


if __name__ == '__main__':
    unittest.main()
