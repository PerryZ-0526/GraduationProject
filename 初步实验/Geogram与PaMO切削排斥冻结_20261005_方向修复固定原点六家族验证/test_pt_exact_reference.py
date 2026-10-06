"""有理数参照解析答案、刚体变换与冻结查询资产检查。"""
import hashlib
import json
import math
from pathlib import Path
import unittest
import numpy as np
from pt_exact_reference import point_triangle_reference


class ExactPointTriangleTests(unittest.TestCase):
    def test_all_seven_features(self):
        triangle=[[0,0,0],[1,0,0],[0,1,0]]
        cases=[([.25,.25,.5],0,.5),([-1,-1,0],1,math.sqrt(2)),([2,0,0],2,1),
            ([.5,-.2,0],3,.2),([0,2,0],4,1),([-.2,.5,0],5,.2),([.6,.6,0],6,math.sqrt(.02))]
        for point,kind,distance in cases:
            with self.subTest(kind=kind):
                result=point_triangle_reference([point,*triangle])
                self.assertEqual(result[0],kind)
                self.assertAlmostEqual(result[1],distance,places=14)

    def test_degenerate_and_true_contact(self):
        self.assertEqual(point_triangle_reference([[.5,.1,0],[0,0,0],[1,0,0],[.5,0,0]])[0],3)
        self.assertAlmostEqual(point_triangle_reference([[1,1,1],[0,0,0],[0,0,0],[0,0,0]])[1],math.sqrt(3))
        self.assertEqual(point_triangle_reference([[.25,.25,0],[0,0,0],[1,0,0],[0,1,0]]),(0,0))

    def test_exact_rigid_transform(self):
        values=np.array([[.5,-.25,0],[0,0,0],[1,0,0],[0,1,0]])
        rotation=np.array([[0,-1,0],[1,0,0],[0,0,1]])
        self.assertEqual(point_triangle_reference(values),point_triangle_reference(values@rotation.T+[2,3,4]))

    def test_frozen_queries_and_reference_hashes(self):
        root=Path(__file__).resolve().parent.parent/"可复用磨削测试集/点三角形精度对拍输入_v1"
        path=root/"01-点三角形精度对拍清单.json"
        digest=json.loads((root/"03-点三角形输入摘要.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest["manifest_sha256"])
        self.assertEqual(hashlib.sha256(Path(__file__).with_name("pt_exact_reference.py").read_bytes()).hexdigest(),digest["reference_source_sha256"])
        cases=json.loads(path.read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases),100)
        for case in cases:
            with self.subTest(id=case["id"]):
                values=np.array(case["positions_normalized"])
                self.assertTrue(np.array_equal(values,values.astype(np.float32).astype(np.float64)))
                kind,distance=point_triangle_reference(values)
                self.assertEqual(kind,case["expected_kind"])
                self.assertAlmostEqual(distance,case["expected_distance"],places=15)


if __name__=="__main__":
    unittest.main()
