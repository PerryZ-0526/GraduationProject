"""后端条件性输入不能放开退化自由面或真实FP64退化面。"""
from pathlib import Path
import json
import unittest
import numpy as np
import trimesh
from preserved_input_repair import require_fixed_degenerate_faces,repair_preserved_input


class PreservedInputTests(unittest.TestCase):
    def test_fixed_quantized_face_allowed_conditionally(self):
        vertices = np.array([[10,0,0],[10+1e-8,0,0],[10,1,0]])
        result = require_fixed_degenerate_faces(vertices,np.array([[0,1,2]]),np.ones(3,bool),1.0,np.zeros(3))
        self.assertEqual(result["encoded_degenerate_faces"],1)

    def test_degenerate_free_face_rejected(self):
        vertices = np.array([[10,0,0],[10+1e-8,0,0],[10,1,0]])
        with self.assertRaises(ValueError):
            require_fixed_degenerate_faces(vertices,np.array([[0,1,2]]),np.array([True,False,True]),1.0,np.zeros(3))

    def test_nonfinite_encoding_rejected(self):
        with np.errstate(over="ignore"),self.assertRaises(ValueError):
            require_fixed_degenerate_faces(np.ones((3,3))*1e100,np.array([[0,1,2]]),np.ones(3,bool),1.0,np.zeros(3))

    def test_existing_ct_repair_keeps_fp64_area_and_labels(self):
        root = Path(__file__).parents[1]/"可复用磨削测试集/CT第六事件浮点退化与能量回归_v1/inputs"
        mesh = trimesh.load(root/"source_original.obj",process=False)
        bits = json.loads((root/"source_original_labels.json").read_text(encoding="utf-8"))["operand_bits"]
        candidate,labels,record = repair_preserved_input(mesh,bits)
        self.assertTrue(record["accepted_for_fixed_geometry_backend"])
        self.assertTrue(record["requires_full_embedding_before_gpu"])
        self.assertFalse(record["published"])
        self.assertEqual(record["remaining_arithmetic_invalid_faces"],6)
        self.assertEqual(record["remaining_fp64_threshold_faces"],0)
        self.assertGreater(candidate.area_faces.min(),1e-12)
        self.assertEqual(len(labels),len(candidate.faces))
        self.assertLessEqual(record["geometry_probe_max_mm"],1e-7)

    def test_true_degenerate_closed_input_rejected(self):
        mesh = trimesh.Trimesh(vertices=np.zeros((4,3)),faces=[[0,2,1],[0,1,3],[0,3,2],[1,2,3]],process=False)
        _,_,record = repair_preserved_input(mesh,np.ones(4,int))
        self.assertFalse(record["accepted_for_fixed_geometry_backend"])


if __name__ == "__main__":
    unittest.main()
