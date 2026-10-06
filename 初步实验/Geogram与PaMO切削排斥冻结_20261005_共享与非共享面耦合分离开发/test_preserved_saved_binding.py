"""完整保存证据缺失、错配或失败不能被输出几何复审接受。"""
import unittest
from unittest.mock import patch
import trimesh
from preserved_saved_binding import collect_certificates,mesh_valid_saved_binding,load_bound_reference
from exact_embedding_gate import stored_mesh_sha256


class PreservedSavedTests(unittest.TestCase):
    def setUp(self):
        self.mesh = trimesh.creation.box()
        self.digest = stored_mesh_sha256(self.mesh)
        self.certificate = dict(saved_sha256=self.digest,embedded_closed=True,execution=dict(returncode=0),
                                parsed=True,topology_valid=True,closed=True,self_intersection_pairs=0)

    def test_matching_successful_certificate(self):
        self.assertTrue(mesh_valid_saved_binding(self.mesh,{self.digest:self.certificate})[0])

    def test_incomplete_failed_and_mismatched_certificate(self):
        for replacement in ({"execution":{"returncode":1}},{"saved_sha256":"wrong"},{"self_intersection_pairs":1},{"parsed":False}):
            with self.subTest(replacement=replacement):
                certificate = dict(self.certificate,**replacement)
                self.assertFalse(mesh_valid_saved_binding(self.mesh,{self.digest:certificate})[0])
        self.assertFalse(mesh_valid_saved_binding(self.mesh,{})[0])

    def test_conflicting_certificates_rejected(self):
        report = dict(rows=[dict(full_exact_embedding=self.certificate),
                           dict(full_exact_embedding=dict(self.certificate,embedded_closed=False))])
        with self.assertRaises(ValueError):
            collect_certificates(report)

    def test_nested_certificates_collected(self):
        report = dict(rows=[dict(metrics=dict(full_exact_embedding=self.certificate))])
        self.assertEqual(collect_certificates(report),{self.digest:self.certificate})

    def test_reference_loading_matches_publication(self):
        with patch("preserved_saved_binding.trimesh.load",return_value=self.mesh) as load:
            load_bound_reference("reference.obj",{})
            load.assert_called_once_with("reference.obj",process=True,validate=True)
        with patch("preserved_saved_binding.trimesh.load",return_value=self.mesh) as load:
            load_bound_reference("validated_reference.obj",dict(reference_used_file="validated_reference.obj"))
            load.assert_called_once_with("validated_reference.obj",process=False,validate=False)


if __name__ == "__main__":
    unittest.main()
