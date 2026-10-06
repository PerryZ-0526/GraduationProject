"""新增短边修复的父锚点、来源、分离守卫和截止预算控制。"""
import unittest
import numpy as np
from short_edge_repair import repair_short_edges
from exact_mesh_memory import ExactMeshMemory


class ShortEdgeTests(unittest.TestCase):
    def setUp(self):
        self.parent=np.array([[0.,0,0],[1.,0,0],[0.,1,0],[0.,0,1]])
        self.vertices=np.vstack((self.parent,[1e-14,0,0]))
        self.faces=np.array([[0,2,4],[4,2,1],[0,4,3],[4,1,3],[1,2,3],[2,0,3]])
        self.bits=np.ones(6,dtype=int)

    def test_new_point_collapses_to_parent_with_exact_output(self):
        v,f,b,record=repair_short_edges(self.vertices,self.faces,self.bits,self.parent,100)
        self.assertEqual(len(record['operations']),1)
        self.assertEqual(record['operations'][0]['keep'],0)
        self.assertTrue(record['operations'][0]['kept_parent_anchor'])
        np.testing.assert_array_equal(v,self.vertices)
        self.assertEqual(len(f),4);self.assertTrue(ExactMeshMemory().audit(v,f)['embedded_closed'])
        self.assertLessEqual(record['geometry_upper_sum_mm'],1.1e-14)

    def test_two_distinct_parent_anchors_remain_fixed(self):
        _,f,_,record=repair_short_edges(self.vertices,self.faces,self.bits,self.vertices,100)
        self.assertEqual(record['operations'],[]);np.testing.assert_array_equal(f,self.faces)

    def test_source_identity_cannot_disappear(self):
        self.bits[0]=3
        _,f,_,record=repair_short_edges(self.vertices,self.faces,self.bits,self.parent,100)
        self.assertEqual(record['operations'],[]);np.testing.assert_array_equal(f,self.faces)

    def test_failed_separation_does_not_commit(self):
        _,f,_,record=repair_short_edges(self.vertices,self.faces,self.bits,self.parent,100,separation_check=lambda *args:False)
        self.assertEqual(record['operations'],[]);np.testing.assert_array_equal(f,self.faces)

    def test_zero_budget_does_not_commit(self):
        _,f,_,record=repair_short_edges(self.vertices,self.faces,self.bits,self.parent,0)
        self.assertEqual(record['operations'],[]);np.testing.assert_array_equal(f,self.faces)


if __name__=='__main__':unittest.main()
