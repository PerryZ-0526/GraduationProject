"""共享顶点面分离的严格侧证书、假锚点和冻结约束回归。"""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import trimesh
from automatic_pair_separation import original_shared_vertex_separator, exact_shared_vertex_separated, project_vertices, project_vertices_coupled, exact_relative_pair_separated
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
    def test_solver_status_does_not_replace_exact_certificate(self):
        with patch('automatic_pair_separation.minimize',return_value=SimpleNamespace(success=False,x=np.array([1.,0,0]))):
            self.assertIsNotNone(original_shared_vertex_separator(self.a,self.b,np.zeros(3)))
    def test_same_side_has_no_separator(self):
        self.assertIsNone(original_shared_vertex_separator(self.a,self.a.copy(),np.zeros(3)))
    def test_shared_anchor_can_move_with_tool_projection(self):
        points=np.vstack([self.a.copy(),self.b[1:]])
        points[1:3,0]=-.01
        mesh=trimesh.Trimesh(points,[[0,1,2],[0,3,4]],process=False)
        constraints=[[([1.,0,0],.1)] for _ in mesh.vertices]
        pairs={(0,1):{'separator_kind':'shared_single_vertex','normal':[1.,0,0],'shared_vertex_id':0}}
        candidate,reason=project_vertices_coupled(mesh,constraints,.3,pairs)
        self.assertIsNone(reason)
        self.assertTrue(exact_shared_vertex_separated(candidate.triangles,[1.,0,0],candidate.vertices[0]))
        self.assertTrue(np.all(candidate.vertices[:,0]>=.1-1e-10))
    def test_disjoint_plane_can_translate_with_tool_constraints(self):
        a=np.array([[-.01,-1,0],[-.01,1,0],[-.01,0,1]])
        b=a.copy();b[:,0]=.01
        mesh=trimesh.Trimesh(np.vstack([a,b]),[[0,1,2],[3,4,5]],process=False)
        constraints=[[([1.,0,0],.1)] for _ in mesh.vertices]
        pairs={(0,1):{'normal':[1.,0,0],'offset':0.}}
        candidate,reason=project_vertices_coupled(mesh,constraints,.3,pairs)
        self.assertIsNone(reason)
        self.assertTrue(exact_relative_pair_separated(candidate.triangles,[1.,0,0]))
    def test_coupled_projection_keeps_original_radius(self):
        mesh=trimesh.Trimesh(self.a,[[0,1,2]],process=False)
        constraints=[[([1.,0,0],.1)] for _ in mesh.vertices]
        candidate,reason=project_vertices_coupled(mesh,constraints,.01,{})
        self.assertIsNone(candidate)
        self.assertEqual(reason['reason'],'infeasible_or_unverified_projection')
if __name__=='__main__':unittest.main()
