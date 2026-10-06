"""使用第三刀真实重复面负例检查严格焊接回退及原成功分支保持。"""
import unittest
from pathlib import Path
import json
import numpy as np
import trimesh
from exact_duplicate_cleanup_fallback import clean_with_exact_duplicate_fallback
from run_canonical_stepwise_feedback import canonical_cleanup

class ExactCleanupTests(unittest.TestCase):
    def test_real_third_event_preserves_coordinates_faces_and_sources(self):
        path=Path('D:/GraduationProject_切削排斥证据/20261005_邻面约束小面修复薄壁完整32刀开发/薄壁_00_长序列/薄壁_00_长序列_e2_candidate_input/source.obj')
        mesh=trimesh.load(path,process=False)
        bits=np.asarray(json.loads(path.with_name('labels.json').read_text('utf8'))['operand_bits'])
        with self.assertRaises(ValueError):canonical_cleanup(mesh,bits,allow_shared=True)
        result,labels,record=clean_with_exact_duplicate_fallback(mesh,bits,allow_shared=True)
        self.assertEqual(record['role'],'exact_coordinate_weld_after_rounded_duplicate_failure')
        self.assertEqual(len(result.faces),len(mesh.faces))
        np.testing.assert_array_equal(np.unique(result.vertices,axis=0),np.unique(mesh.vertices,axis=0))
        self.assertEqual(sorted(labels.tolist()),sorted(bits.tolist()))
        self.assertTrue(result.is_watertight and result.is_winding_consistent)
        self.assertEqual(result.euler_number,mesh.euler_number)
    def test_original_success_is_identical(self):
        mesh=trimesh.creation.icosphere(subdivisions=1)
        bits=np.ones(len(mesh.faces),dtype=int)
        expected,labels,record=canonical_cleanup(mesh,bits,allow_shared=True)
        actual,new_labels,new_record=clean_with_exact_duplicate_fallback(mesh,bits,allow_shared=True)
        np.testing.assert_array_equal(expected.vertices,actual.vertices)
        np.testing.assert_array_equal(expected.faces,actual.faces)
        np.testing.assert_array_equal(labels,new_labels)
        self.assertEqual(record,new_record)
    def test_actual_duplicate_faces_remain_rejected(self):
        mesh=trimesh.creation.icosphere(subdivisions=1)
        mesh=trimesh.Trimesh(mesh.vertices,np.vstack([mesh.faces,mesh.faces[0]]),process=False)
        with self.assertRaises(ValueError):clean_with_exact_duplicate_fallback(mesh,np.ones(len(mesh.faces),dtype=int),allow_shared=True)

if __name__=='__main__':unittest.main()
