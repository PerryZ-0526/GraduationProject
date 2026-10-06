"""核对诊断对照的几何等价、闭合性及不可覆盖约定。"""

from pathlib import Path
import tempfile
import unittest

import numpy as np
import trimesh

from build_causal_cases import build, digest


class CausalAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "诊断输入"
        self.manifest = build(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_same_convex_prism_different_triangulations(self):
        for pair in self.manifest["pairs"]:
            first, second = [trimesh.load(self.root / entry["mesh"], force="mesh", process=False)
                             for entry in pair["meshes"]]
            # 凸四边形两种对角线均划分同一多边形，闭合柱体坐标集合必须相同。
            polygon = np.asarray(pair["polygon_xy_mm"])
            edges = np.roll(polygon, -1, axis=0) - polygon
            turns = edges[:, 0] * np.roll(edges, -1, axis=0)[:, 1] - edges[:, 1] * np.roll(edges, -1, axis=0)[:, 0]
            self.assertTrue(np.all(turns > 0))
            self.assertEqual(set(map(tuple, first.vertices)), set(map(tuple, second.vertices)))
            self.assertAlmostEqual(first.volume, second.volume, places=12)
            self.assertAlmostEqual(first.area, second.area, places=12)
            self.assertNotEqual({tuple(sorted(map(tuple, t))) for t in first.triangles},
                                {tuple(sorted(map(tuple, t))) for t in second.triangles})
            for mesh in (first, second):
                self.assertTrue(mesh.is_watertight and mesh.is_winding_consistent)
                self.assertEqual(mesh.euler_number, 2)
                self.assertTrue(np.all(mesh.area_faces > 1e-12))

    def test_mesh_and_tool_hashes_match_saved_files(self):
        for pair in self.manifest["pairs"]:
            for entry in pair["meshes"] + pair["tools"]:
                self.assertEqual(digest(self.root / entry["mesh"]), entry["sha256"])
                mesh = trimesh.load(self.root / entry["mesh"], force="mesh", process=False)
                self.assertTrue(mesh.is_watertight and np.isfinite(mesh.vertices).all())

    def test_existing_assets_cannot_be_overwritten(self):
        path = self.root / "01-同几何因果测试清单.json"
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            build(self.root)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
