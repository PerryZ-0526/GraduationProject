"""活动面限制同时约束种子与邻接传播，外部面保留不依赖GPU日志。"""
import unittest
import numpy as np
import trimesh
from constrained_quality import fixed_surface_contract
from planar_active_patch import SOURCE,rebuild_planar_regions


class ActivePatchTests(unittest.TestCase):
    def test_saved_recheck_keeps_numerical_and_original_external_checks(self):
        from pathlib import Path
        import recheck_ordered_features
        from recheck_active_patch_projection import build_recheck
        source=build_recheck(Path(recheck_ordered_features.__file__).read_text(encoding='utf-8'))
        compile(source,'active_saved_recheck','exec')
        for marker in ('check_initial_encoding_record',"row['numerical_diagnostic']['passed']",
            'mesh_valid_saved_binding',"external['passed']", "4 if method=='expanded' else 2",'len(actual)!=6'):
            self.assertIn(marker,source)
        self.assertNotIn('feature_width_mm',source)

    def test_full_fallback_dispatch_remains_original_method(self):
        from unittest.mock import patch
        from run_active_patch_projection import ActivePatchEngine
        from run_initial_encoding_projection import InitialEncodingEngine
        engine=ActivePatchEngine.__new__(ActivePatchEngine)
        with patch.object(InitialEncodingEngine,'run',return_value={'method':'full'}) as run:
            self.assertEqual(engine.run(None,None,None,'full',None),{'method':'full'})
            self.assertEqual(run.call_args.args[3],'full')

    def test_seed_and_frontier_both_restricted(self):
        self.assertIn('not active[seed]',SOURCE)
        self.assertIn('face in visited or not active[face]',SOURCE)

    def test_single_active_triangle_cannot_expand_to_external_coplanar_face(self):
        source=trimesh.creation.box()
        active=np.zeros(len(source.faces),bool);active[0]=True
        fixed=np.zeros(len(source.vertices),bool);fixed[np.unique(source.faces[~active])]=True
        output,bits,details=rebuild_planar_regions(source,np.ones(len(source.faces),int),active,min_area_mm2=1e-12)
        np.testing.assert_array_equal(output.vertices,source.vertices)
        np.testing.assert_array_equal(output.faces,source.faces)
        self.assertEqual(details['eligible_regions'],0)
        self.assertTrue(fixed_surface_contract(source,output,active,fixed)['passed'])

    def test_empty_activity_is_identity(self):
        source=trimesh.creation.box()
        output,bits,details=rebuild_planar_regions(source,np.ones(len(source.faces),int),np.zeros(len(source.faces),bool))
        np.testing.assert_array_equal(output.vertices,source.vertices)
        np.testing.assert_array_equal(output.faces,source.faces)
        self.assertEqual(details['eligible_regions'],0)


if __name__=='__main__':
    unittest.main()
