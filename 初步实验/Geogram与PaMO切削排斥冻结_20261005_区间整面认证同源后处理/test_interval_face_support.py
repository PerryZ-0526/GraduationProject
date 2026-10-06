"""解析边界、浮点消去、次正规数与原有理数证明对拍。"""
import unittest
from pathlib import Path
import sys
import numpy as np
import trimesh
from cut_exclusion import certify_face_support
# 冻结启动器不自动加入诊断入口目录，显式绑定本目录证明实现。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from interval_face_support import certify_face_support_interval


class IntervalSupportTests(unittest.TestCase):
    def compare(self, vertices, normals, offsets, selected=None):
        mesh = trimesh.Trimesh(vertices, np.arange(len(vertices)).reshape((-1, 3)), process=False)
        chosen = np.zeros(len(mesh.faces), int) if selected is None else selected
        original = certify_face_support(mesh, np.asarray(normals), np.asarray(offsets), chosen)
        result = certify_face_support_interval(mesh, normals, offsets, chosen)
        for key in ('passed', 'failed_face_count', 'failed_face_ids', 'certified_scope'):
            self.assertEqual(result[key], original[key])
        return result

    def test_whole_face_rejects_single_inside_vertex(self):
        result = self.compare([(1, 0, 0), (1, 1, 0), (-1, 0, 1)], [(1, 0, 0)], [0])
        self.assertFalse(result['passed'])

    def test_exact_boundary_falls_back(self):
        result = self.compare([(0, 0, 0), (0, 1, 0), (0, 0, 1)], [(1, 0, 0)], [0])
        self.assertTrue(result['passed'])
        self.assertGreater(result['exact_fallback_pair_count'], 0)

    def test_cancellation_near_large_coordinate(self):
        result = self.compare([(2**53, 1, 0), (2**53, 1, 1), (2**53, 1, 2)], [(1, 1, 0)], [float(2**53 + 2)])
        self.assertFalse(result['passed'])
        self.assertGreater(result['exact_fallback_pair_count'], 0)

    def test_subnormal_product(self):
        tiny = np.nextafter(0., 1.)
        result = self.compare([(tiny, 0, 0), (tiny, 1, 0), (tiny, 0, 1)], [(.5, 0, 0)], [tiny])
        self.assertFalse(result['passed'])

    def test_selected_planes_and_random_cases(self):
        rng = np.random.default_rng(20261005)
        for _ in range(20):
            self.compare(rng.normal(size=(30, 3)), rng.normal(size=(4, 3)), rng.normal(size=4), rng.integers(0, 4, size=10))


if __name__ == '__main__':
    unittest.main()
