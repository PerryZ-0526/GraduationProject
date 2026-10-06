"""相邻小面修复的支撑方向、闭合性和默认规则回归。"""
import unittest
import numpy as np
import trimesh
from locality_sliver_collapse import collapse_degenerate,exact_unit_normal
from locality_retriangulate import invalid_faces


def subdivided_box_edge():
    """在一个盒边插入两个邻近点，两侧三角面同步细分以保持闭合。"""
    mesh=trimesh.creation.box()
    a,b=map(int,mesh.faces[0][:2])
    points=mesh.vertices.tolist()
    p,q=len(points),len(points)+1
    points.extend([(mesh.vertices[a]+t*(mesh.vertices[b]-mesh.vertices[a])).tolist() for t in (1e-13,2e-13)])
    faces=[]
    for face in mesh.faces:
        if a in face and b in face:
            c=int(next(i for i in face if i not in (a,b)))
            forward=any(int(u)==a and int(v)==b for u,v in zip(face,np.roll(face,-1)))
            chain=[a,p,q,b] if forward else [b,q,p,a]
            faces.extend([[u,v,c] for u,v in zip(chain,chain[1:])])
        else:
            faces.append(face.tolist())
    return trimesh.Trimesh(points,faces,process=False)


class SmallIncidentCollapseTests(unittest.TestCase):
    def test_tiny_plane_direction_is_stable(self):
        normal=exact_unit_normal(np.array([[0,0,0],[1e-13,0,0],[0,1e-13,0]]))
        np.testing.assert_array_equal(normal,[0,0,1])

    def test_exactly_collinear_rejected(self):
        self.assertIsNone(exact_unit_normal(np.array([[0,0,0],[1,0,0],[2,0,0]])))

    def test_adjacent_small_faces_repair(self):
        mesh=subdivided_box_edge()
        self.assertTrue(mesh.is_watertight)
        self.assertGreater(int(invalid_faces(mesh.vertices,mesh.faces).sum()),0)
        result,labels,record=collapse_degenerate(mesh,np.ones(len(mesh.faces),int),allow_small_incident=True)
        self.assertTrue(result.is_watertight)
        self.assertTrue(result.is_winding_consistent)
        self.assertEqual(result.euler_number,mesh.euler_number)
        self.assertEqual(record["remaining_invalid_faces"],0)
        self.assertEqual(len(labels),len(result.faces))
        self.assertAlmostEqual(result.volume,mesh.volume)


if __name__=="__main__":
    unittest.main()
