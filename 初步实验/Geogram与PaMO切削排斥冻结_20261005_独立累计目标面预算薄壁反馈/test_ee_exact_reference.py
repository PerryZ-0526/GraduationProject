"""端点、内部、平行和退化闭线段的距离参照控制。"""
import unittest
from ee_exact_reference import edge_edge_reference


class EdgeReferenceTests(unittest.TestCase):
    def test_crossing(self):
        self.assertEqual(edge_edge_reference([[-1,0,0],[1,0,0],[0,-1,0],[0,1,0]]), (8,0.0))

    def test_skew_interior(self):
        self.assertEqual(edge_edge_reference([[-1,0,0],[1,0,0],[0,-1,2],[0,1,2]]), (8,2.0))

    def test_disjoint_endpoints(self):
        self.assertEqual(edge_edge_reference([[0,0,0],[1,0,0],[3,0,0],[4,0,0]]), (2,2.0))

    def test_parallel_overlap(self):
        self.assertEqual(edge_edge_reference([[0,0,0],[2,0,0],[.5,1,0],[1.5,1,0]])[1],1.0)

    def test_two_points(self):
        self.assertEqual(edge_edge_reference([[0,0,0],[0,0,0],[0,0,3],[0,0,3]]), (0,3.0))

    def test_nearly_parallel_small_gap(self):
        self.assertAlmostEqual(edge_edge_reference([[0,0,0],[1,0,0],[0,1e-9,0],[1,1.0000001e-9,0]])[1],1e-9,places=18)


if __name__ == "__main__":
    unittest.main()
