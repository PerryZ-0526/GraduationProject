"""反向面消解只接受两面同来源，禁止以重复面清理掩盖真实来源冲突。"""
import unittest
import numpy as np
import json
from pathlib import Path
import trimesh
from opposed_facet_cleanup import opposed_pairs,clean_cancel_opposed


class OpposedFacetTests(unittest.TestCase):
    def test_opposite_same_source(self):
        self.assertEqual(opposed_pairs(np.array([[0,1,2],[1,0,2]]),np.array([3,3])),[[0,1]])

    def test_same_orientation_rejected(self):
        with self.assertRaisesRegex(ValueError,"同向"):
            opposed_pairs(np.array([[0,1,2],[1,2,0]]),np.array([1,1]))

    def test_source_conflict_rejected(self):
        with self.assertRaisesRegex(ValueError,"同来源"):
            opposed_pairs(np.array([[0,1,2],[1,0,2]]),np.array([1,2]))

    def test_multiple_faces_rejected(self):
        with self.assertRaisesRegex(ValueError,"恰好两个"):
            opposed_pairs(np.array([[0,1,2],[1,0,2],[2,0,1]]),np.array([2,2,2]))

    def test_no_duplicates_identity(self):
        self.assertEqual(opposed_pairs(np.array([[0,1,2],[1,2,3]]),np.array([1,2])),[])

    def test_closed_mesh_matches_original_cleanup(self):
        mesh=trimesh.creation.box()
        result,bits,record=clean_cancel_opposed(mesh,np.ones(len(mesh.faces),int))
        self.assertTrue(result.is_watertight)
        self.assertEqual(len(bits),len(mesh.faces))
        self.assertNotIn("cancelled_opposed_original_face_pairs",record)

    def test_six_frozen_source_failures(self):
        # 六组已见故障资产均作实际整网格检查，不把它们算作未见评价。
        root=Path(__file__).resolve().parent.parent/"可复用磨削测试集/来源重复面回归输入_v1"
        cases=json.loads((root/"01-来源重复面回归资产清单.json").read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases),6)
        for case in cases:
            with self.subTest(case=case["id"]):
                roles={item["role"]:root/item["file"] for item in case["files"]}
                mesh=trimesh.load(roles["source"],force="mesh",process=False)
                bits=json.loads(roles["labels"].read_text(encoding="utf-8"))["operand_bits"]
                result,labels,record=clean_cancel_opposed(mesh,bits,allow_shared=True)
                self.assertEqual(len(record["cancelled_opposed_original_face_pairs"]),1)
                self.assertTrue(record["topology_preserved"])
                self.assertTrue(result.is_watertight)
                self.assertEqual(len(labels),len(result.faces))
                self.assertLessEqual(record["raw_to_clean_geometry"]["probe_max_mm"],1e-7)


if __name__=="__main__":
    unittest.main()
