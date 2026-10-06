"""逆向漏覆盖补点的边界共形与重复执行控制。"""

import unittest
import numpy as np
import trimesh

from reverse_coverage_seeds import insert_reverse_coverage_seeds


class ReverseCoverageTests(unittest.TestCase):
    def test_missing_peak_preserves_boundary_and_is_not_reinserted(self):
        mesh = trimesh.Trimesh([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]], [[0, 1, 2]], process=False)
        # 开放解析三角形只验证插入算子；运行候选必须另作闭合嵌入和目标几何验收。
        target = trimesh.Trimesh([[.25, .25, .3]], np.empty((0, 3), dtype=int), process=False)
        result, record = insert_reverse_coverage_seeds(mesh, target)
        self.assertEqual(record["inserted_vertices"], 1)
        self.assertTrue(np.array_equal(result.vertices[:3], mesh.vertices))
        self.assertTrue(np.array_equal(result.vertices[-1], target.vertices[0]))
        boundary = {tuple(edge) for edge, count in zip(result.edges_unique,
            np.bincount(result.edges_unique_inverse)) if count == 1}
        self.assertEqual(boundary, {(0, 1), (0, 2), (1, 2)})
        self.assertTrue(np.all(result.area_faces > 0))
        again, second = insert_reverse_coverage_seeds(result, target)
        self.assertEqual(second["inserted_vertices"], 0)
        self.assertTrue(np.array_equal(again.vertices, result.vertices))
        self.assertTrue(np.array_equal(again.faces, result.faces))


if __name__ == "__main__":
    unittest.main()
