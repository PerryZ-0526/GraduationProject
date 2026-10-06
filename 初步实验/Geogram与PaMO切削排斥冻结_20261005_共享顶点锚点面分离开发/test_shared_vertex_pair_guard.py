"""共享顶点面分离的严格侧证书、假锚点和冻结约束回归。"""
import unittest
import numpy as np
import trimesh
from automatic_pair_separation import original_shared_vertex_separator, exact_shared_vertex_separated, project_vertices
class SharedVertexTests(unittest.TestCase):
    def setUp(self):
        self.a=np.array([[0.,0,0],[-1,-1,0],[-1,1,0]])
        self.b=np.array([[0.,0,0],[1,-1,0],[1,1,0]])
    def test_original_single_contact_has_separator(self):
        p=original_shared_vertex_separator(self.a,self.b,np.zeros(3))
        self.assertIsNotNone(p)
        self.assertTrue(exact_shared_vertex_separated((self.a,self.b),p['normal'],np.zeros(3)))
    def test_translated_anchor_is_exact(self):
        anchor=np.array([.125,.25,.5])
        p=original_shared_vertex_separator(self.a+anchor,self.b+anchor,anchor)
        self.assertIsNotNone(p)
        self.assertTrue(exact_shared_vertex_separated((self.a+anchor,self.b+anchor),p['normal'],anchor))
    def test_crossing_face_is_rejected(self):
        b=self.b.copy();b[1]=[-.5,0,0]
        self.assertFalse(exact_shared_vertex_separated((self.a,b),[1.,0,0],np.zeros(3)))
    def test_fake_plane_anchor_is_rejected(self):
        self.assertFalse(exact_shared_vertex_separated((self.a,self.b),[1.,0,0],[0.,0,1]))
    def test_same_side_has_no_separator(self):
        self.assertIsNone(original_shared_vertex_separator(self.a,self.a.copy(),np.zeros(3)))
    def test_fixed_anchor_must_satisfy_tool_constraints(self):
        mesh=trimesh.Trimesh(self.a,[[0,1,2]],process=False)
        constraints=[[([1.,0,0],.1)] for _ in mesh.vertices]
        candidate,reason=project_vertices(mesh,constraints,.3,{0:np.zeros(3)})
        self.assertIsNone(candidate)
        self.assertEqual(reason['reason'],'fixed_shared_anchor_conflicts_with_constraints')
if __name__=='__main__':unittest.main()
