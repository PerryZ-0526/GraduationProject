"""自身正面积输入与继承精确零面覆盖规则的控制。"""
import unittest
import numpy as np
import trimesh
from covered_zero_cleanup import clean_arrays
from numeric_input import check_and_boxes
from benchmark import quality


class CoveredZeroTests(unittest.TestCase):
    def test_covered_zero_edge(self):
        mesh=trimesh.creation.box();a,b=mesh.faces[0,:2]
        faces=np.vstack((mesh.faces,[a,a,b]));bits=np.ones(len(faces),dtype=int)
        v,f,labels,info=clean_arrays(np.asarray(mesh.vertices),faces,bits)
        self.assertEqual(info['removed_faces'],1)
        np.testing.assert_array_equal(v[f],mesh.triangles)
        self.assertTrue(trimesh.Trimesh(v,f,process=False).is_watertight)
        self.assertEqual(info['geometric_image_change_mm'],0)

    def test_cross_label_rejected(self):
        mesh=trimesh.creation.box();a,b=mesh.faces[0,:2]
        faces=np.vstack((mesh.faces,[a,a,b]));bits=np.ones(len(faces),dtype=int);bits[-1]=2
        with self.assertRaises(ValueError):clean_arrays(np.asarray(mesh.vertices),faces,bits)

    def test_distinct_collinear_not_removed(self):
        v=np.array([[0.,0,0],[1.,0,0],[2.,0,0]])
        _,f,_,info=clean_arrays(v,np.array([[0,1,2]]),np.array([1]))
        self.assertEqual(len(f),1);self.assertEqual(info['removed_faces'],0)

    def test_positive_area_keeps_tiny_triangle_and_quality_denominator(self):
        v=np.array([[0.,0,0],[1.,0,0],[0.,1e-14,0]]);f=np.array([[0,1,2]])
        self.assertEqual(check_and_boxes(v,f)[0],1)
        self.assertEqual(check_and_boxes(v,f,0)[0],0)
        q=quality(v,f,0);self.assertEqual(q['invalid'],0);self.assertEqual(q['10']['count'],1)
        v[2]=v[1];self.assertEqual(check_and_boxes(v,f,0)[0],1)


if __name__=='__main__':unittest.main()
