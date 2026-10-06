"""新的保留输入应几何有效、完整冻结并区别于已见35体。"""
import json
from pathlib import Path
import unittest
import numpy as np
import trimesh
from build_cases import digest
from build_initial_encoding_holdout import FAMILIES

ROOT=Path(__file__).resolve().parent/'初态编码锚点新参数保留12路线_v1'


class InitialHoldoutTests(unittest.TestCase):
    def test_complete_plan_and_new_body_hashes(self):
        report=json.loads((ROOT/'01-完整范围冻结清单.json').read_text(encoding='utf-8'))
        old=json.loads((ROOT.parent/'合成输入_v1/01-测试集清单.json').read_text(encoding='utf-8'))
        routes=report['routes']
        self.assertEqual(len(routes),12)
        self.assertEqual(tuple(r['family'] for r in routes),FAMILIES)
        self.assertTrue(all(len(r['cutting_prefix_ids'])==4 for r in routes))
        self.assertEqual(len({r['initial_mesh_sha256'] for r in routes}),12)
        self.assertTrue({r['initial_mesh_sha256'] for r in routes}.isdisjoint({b['sha256'] for b in old['bodies']}))

    def test_frozen_valid_meshes(self):
        report=json.loads((ROOT/'01-完整范围冻结清单.json').read_text(encoding='utf-8'))
        for route in report['routes']:
            for name,expected in [(route['initial_mesh'],route['initial_mesh_sha256']),
                *[(t['mesh'],t['sha256']) for t in route['prefix_tools']]]:
                path=ROOT/'inputs'/name
                self.assertEqual(digest(path),expected)
                mesh=trimesh.load(path,process=False)
                self.assertTrue(mesh.is_watertight and mesh.is_winding_consistent)
                self.assertTrue(np.isfinite(mesh.vertices).all())
                self.assertTrue(np.all(mesh.area_faces>1e-12))

    def test_source_based_anchor_and_recorded_endpoints(self):
        report=json.loads((ROOT/'01-完整范围冻结清单.json').read_text(encoding='utf-8'))
        for route in report['routes']:
            mesh=trimesh.load(ROOT/'inputs'/route['initial_mesh'],process=False)
            anchor=route['cut_anchor']
            np.testing.assert_allclose(anchor['surface_anchor_mm'],mesh.triangles_center[anchor['source_face_index']],atol=1e-14)
            self.assertEqual([e['id'] for e in route['events']],route['cutting_prefix_ids'])
            self.assertTrue(all(e['cutting'] for e in route['events']))
            # 原表面锚点严格处于每段离散凸工具内，排除高处空走的伪接触案例。
            point=np.asarray(anchor['surface_anchor_mm'])
            for tool in route['prefix_tools']:
                tool_mesh=trimesh.load(ROOT/'inputs'/tool['mesh'],process=False)
                self.assertTrue(tool_mesh.is_convex)
                offsets=np.einsum('ij,ij->i',tool_mesh.triangles_center,tool_mesh.face_normals)
                self.assertLess(float(np.max(point@tool_mesh.face_normals.T-offsets)),0.)


if __name__=='__main__':
    unittest.main()
