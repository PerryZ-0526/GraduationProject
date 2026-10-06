"""检查资产生成、清单划分及运动到连续输入的可重复转换。"""

import tempfile
import unittest
from pathlib import Path
import numpy as np
from build_cases import make_body, routes
from prepare_feedback import make_route, save_obj_fp64


class ReusableCasesTests(unittest.TestCase):
    def test_all_families_valid_and_deterministic(self):
        for family in ("板体", "球体", "椭球", "弯曲骨样体", "贯通孔", "薄壁", "窄缝"):
            for variant in range(5):
                mesh = make_body(family, variant)
                self.assertTrue(mesh.is_watertight, (family, variant))
                self.assertTrue(mesh.is_winding_consistent)
                np.testing.assert_array_equal(mesh.vertices, make_body(family, variant).vertices)

    def test_route_tool_conversion_preserves_segments(self):
        mesh = make_body("板体", 0)
        name, points, radius = routes(mesh)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = root / "initial.obj"
            save_obj_fp64(mesh, initial)
            motion = {"tool_radius_mm": radius, "events": [{"position_mm": p.tolist()} for p in points[:3]]}
            route = make_route({"id": "test"}, name, motion, initial, root, "development", "synthetic")
            self.assertEqual(len(route["events"]), 2)
            self.assertEqual(len(route["prefix_tools"]), 2)
            np.testing.assert_array_equal(route["events"][0]["explicit_sweep_start_mm"], points[0])
            np.testing.assert_array_equal(route["events"][0]["position_mm"], points[1])
            self.assertEqual(route["tool"]["mesh_subdivisions"], 3)


if __name__ == "__main__":
    unittest.main()
