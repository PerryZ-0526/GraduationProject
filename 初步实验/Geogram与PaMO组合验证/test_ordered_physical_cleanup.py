"""清理顺序回归保留实际负例、来源拒绝和原版分支。"""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import trimesh
import ordered_physical_cleanup as ordered
from opposed_facet_cleanup import clean_cancel_opposed


class OrderedCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent/'可复用磨削测试集/CT第十八事件清理顺序回归_v1'
        cls.manifest = json.loads((cls.root/'01-清理顺序回归资产清单.json').read_text(encoding='utf-8'))

    def test_frozen_real_inputs_match(self):
        self.assertEqual(len(self.manifest['files']), 5)
        for item in self.manifest['files']:
            self.assertEqual(hashlib.sha256((self.root/item['file']).read_bytes()).hexdigest(), item['sha256'])

    def test_real_failure_repaired_before_joint_gate(self):
        mesh = trimesh.load(self.root/'inputs/source.obj', process=False)
        bits = json.loads((self.root/'inputs/labels.json').read_text(encoding='utf-8'))['operand_bits']
        vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
        with self.assertRaisesRegex(ValueError, '全网格或原实体拓扑'):
            clean_cancel_opposed(mesh, bits, allow_shared=True)
        clean, labels, record = ordered.clean_for_backend(mesh, bits, 'candidate')
        self.assertTrue(record['topology_preserved'])
        self.assertTrue(record['physical_repair_before_joint_check']['accepted_for_fixed_geometry_backend'])
        self.assertEqual(int((clean.area_faces <= 1e-12).sum()), 0)
        self.assertEqual(len(labels), len(clean.faces))
        self.assertTrue(np.isin(labels, [1, 2, 3]).all())
        self.assertLessEqual(record['raw_to_clean_geometry']['probe_max_mm'], 1e-7)
        self.assertNotIn('surviving_original_face_ids', record)
        np.testing.assert_array_equal(mesh.vertices, vertices)
        np.testing.assert_array_equal(mesh.faces, faces)

    def test_valid_mesh_unchanged(self):
        mesh = trimesh.creation.box()
        clean, labels, record = ordered.clean_for_backend(mesh, np.ones(len(mesh.faces), int), 'candidate')
        np.testing.assert_array_equal(clean.faces, mesh.faces)
        np.testing.assert_array_equal(clean.vertices, mesh.vertices)
        self.assertEqual(record['physical_backend_repair']['steps'], [])

    def test_conflicting_opposed_sources_rejected(self):
        mesh = trimesh.creation.box()
        faces = np.vstack([mesh.faces, mesh.faces[0], mesh.faces[0][::-1]])
        bits = np.ones(len(faces), int)
        bits[-1] = 2
        # 三重及不同来源的面禁止靠新顺序吞掉；最终物理检查不能代替来源契约。
        with self.assertRaisesRegex(ValueError, '同来源'):
            ordered.clean_for_backend(trimesh.Trimesh(mesh.vertices, faces, process=False), bits, 'candidate')

    def test_original_branch_delegated(self):
        with patch.object(ordered, 'original_clean_for_backend', return_value='original') as original:
            self.assertEqual(ordered.clean_for_backend('mesh', 'bits', 'full'), 'original')
            original.assert_called_once_with('mesh', 'bits', 'full')


if __name__ == '__main__':
    unittest.main()
