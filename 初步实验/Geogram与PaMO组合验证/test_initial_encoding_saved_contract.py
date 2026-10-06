"""保存对象初态编码锚点不能通过修改数量或任意固定点伪造。"""
import unittest
import numpy as np
from initial_encoding_saved_contract import check_initial_encoding_record


class InitialSavedContractTests(unittest.TestCase):
    def setUp(self):
        self.vertices = np.array([[1., 0., 0.], [1.+1e-8, 0., 0.], [1., 1., 0.], [0.,0.,1.]])
        self.source = np.array([[0.,0.,0.],[1.,1.,1.]])
        self.record = dict(added_vertices=[1,2], precondition=dict(encoded_degenerate_faces=1,all_degenerate_vertices_fixed=True))

    def check(self, output=None):
        return check_initial_encoding_record(self.source,self.vertices,[[0,1,2]],
            self.vertices if output is None else output,[0,-1,-1,-1],self.record)['passed']

    def test_valid_initial_points(self):
        self.assertTrue(self.check())

    def test_moved_anchor_rejected(self):
        output=self.vertices.copy();output[1,0]+=1e-9
        self.assertFalse(self.check(output))

    def test_unrelated_anchor_rejected(self):
        self.record['added_vertices']=[3]
        self.assertFalse(self.check())

    def test_false_count_rejected(self):
        self.record['precondition']['encoded_degenerate_faces']=0
        self.assertFalse(self.check())

    def test_physical_zero_rejected(self):
        self.vertices[1]=self.vertices[0]
        self.assertFalse(self.check())


if __name__ == '__main__':
    unittest.main()
