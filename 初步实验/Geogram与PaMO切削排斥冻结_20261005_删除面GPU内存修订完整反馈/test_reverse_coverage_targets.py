"""闭合解析凸起的逆向目标恢复与重复执行控制。"""

import unittest
import numpy as np
import trimesh

from reverse_coverage_targets import restore_reverse_coverage_targets


class ReverseTargetTests(unittest.TestCase):
    def test_closed_missing_tip_recovers_without_changing_connections(self):
        mesh = trimesh.convex.convex_hull(np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]))
        target = mesh.copy()
        tip = int(np.argmax(target.vertices[:, 2]))
        target.vertices[tip, 2] = 1.3
        result, record = restore_reverse_coverage_targets(mesh, target)
        self.assertEqual(record["relocated_vertices"], 1)
        self.assertTrue(np.array_equal(result.faces, mesh.faces))
        self.assertTrue(np.array_equal(result.vertices, target.vertices))
        self.assertTrue(result.is_watertight)
        self.assertEqual(result.euler_number, mesh.euler_number)
        again, second = restore_reverse_coverage_targets(result, target)
        self.assertEqual(second["relocated_vertices"], 0)
        self.assertTrue(np.array_equal(again.vertices, result.vertices))


if __name__ == "__main__":
    unittest.main()
