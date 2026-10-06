"""验证共享接触证明不会排除实际重叠或跨面穿越。"""
import unittest
import numpy as np
from exact_alarm_contact import prove_contact


class ContactTests(unittest.TestCase):
    def test_shared_edge(self):
        v = np.array([[0,0,0],[1,0,0],[0,1,0],[0,-1,0]], float)
        self.assertEqual(prove_contact(v,[0,1,2],[1,0,3])["kind"], "shared_simplex_only")

    def test_shared_vertex(self):
        v = np.array([[0,0,0],[1,0,0],[0,1,0],[-1,0,0],[0,-1,0]], float)
        self.assertTrue(prove_contact(v,[0,1,2],[0,3,4])["proved"])

    def test_overlap_with_shared_edge(self):
        v = np.array([[0,0,0],[1,0,0],[0,1,0],[.2,.5,0]], float)
        self.assertFalse(prove_contact(v,[0,1,2],[0,1,3])["proved"])

    def test_crossing(self):
        v = np.array([[0,0,0],[2,0,0],[0,2,0],[.5,.5,-1],[.5,.5,1],[1,.5,0]], float)
        self.assertFalse(prove_contact(v,[0,1,2],[3,4,5])["proved"])

    def test_tiny_strict_gap(self):
        v = np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1e-20],[1,0,1e-20],[0,1,1e-20]], float)
        self.assertEqual(prove_contact(v,[0,1,2],[3,4,5])["kind"], "strict_separation")

    def test_shared_vertex_with_interior_crossing(self):
        v = np.array([[0,0,0],[2,0,0],[0,2,0],[1,1,-1],[1,1,1]], float)
        self.assertFalse(prove_contact(v,[0,1,2],[0,3,4])["proved"])

    def test_duplicate_triangles_not_cleared(self):
        v = np.array([[0,0,0],[1,0,0],[0,1,0]], float)
        self.assertFalse(prove_contact(v,[0,1,2],[0,1,2])["proved"])

    def test_folded_shared_edge(self):
        v = np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]], float)
        self.assertTrue(prove_contact(v,[0,1,2],[1,0,3])["proved"])

    def test_same_coordinate_shared_edge_unresolved(self):
        v = np.array([[0,0,0],[0,0,0],[1,0,0],[0,1,0]],float)
        self.assertFalse(prove_contact(v,[0,1,2],[0,1,3])["proved"])


if __name__ == "__main__":
    unittest.main()
