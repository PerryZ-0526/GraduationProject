"""真实失败几何、编号置换与尖角负例验证，不替代GPU完整连续评价。"""
from pathlib import Path
import unittest
import numpy as np,trimesh
from contact_conditioning_geometry import endpoint_collapse,bad_contact_edges
class GeometryConditioningTests(unittest.TestCase):
 def setUp(self):
  p=Path('D:/GraduationProject_切削排斥证据/20261006_二次幂第三阶段薄壁完整32刀开发/薄壁_00_长序列/e1_stage3_working_sources/候选实际Warp编码.obj');self.mesh=trimesh.load(p,process=False);self.q=self.mesh.vertices.astype(np.float32);self.faces=self.mesh.faces
 def test_actual_failed_edge_preserves_other_vertices(self):
  result,r=endpoint_collapse(self.q,self.faces,(280,281),self.q,.0625);self.assertIsNotNone(result);v,f,q=result;ids=np.asarray(r['remaining_original_vertex_ids']);self.assertTrue(np.array_equal(v,self.q[ids]));self.assertTrue(np.array_equal(q,self.q[ids]));self.assertEqual((len(v),len(f)),(1625,3246));self.assertLessEqual(r['max_original_incident_plane_deviation_mm'],1e-8)
 def test_contact_order_and_point_numbering_do_not_select_magic_ids(self):
  permutation=np.random.default_rng(31).permutation(len(self.q));inverse=np.argsort(permutation);q=self.q[permutation];f=inverse[self.faces];ids=np.asarray([[280,281,271,282]]);edges=bad_contact_edges(inverse[ids],np.asarray([[4,8]]),q);self.assertEqual(set(permutation[list(edges[0])]),{280,281});result,r=endpoint_collapse(q,f,edges[0],q,.0625);self.assertIsNotNone(result)
 def test_other_contact_class_is_not_reclassified(self):
  self.assertEqual(bad_contact_edges(np.asarray([[280,281,271,282]]),np.asarray([[4,0]]),self.q),[])
 def test_large_sharp_edge_not_collapsed_by_loosening_plane_budget(self):
  m=trimesh.creation.icosphere(subdivisions=0,radius=1);edge=m.edges_unique[0];result,r=endpoint_collapse(m.vertices,m.faces,edge,m.vertices.astype(np.float32),1);self.assertIsNone(result);self.assertEqual(r['reason'],'no_legal_endpoint');self.assertIn('original_plane_budget',r['rejections'])
if __name__=='__main__':unittest.main()
