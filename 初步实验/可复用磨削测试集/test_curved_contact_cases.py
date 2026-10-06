"""弯曲体补充输入必须有真实几何接触，空接触和重复参数不能伪装通过。"""
from pathlib import Path
import tempfile
import unittest
import trimesh
from build_curved_contact_cases import build, contact_witness


class CurvedContactTests(unittest.TestCase):
    def test_surface_anchored_route(self):
        with tempfile.TemporaryDirectory() as temp:
            result = build(Path(temp)/"asset", parameters=(2.4,))
            route = result["routes"][0]
            self.assertEqual(len(route["prefix_tools"]), 3)
            self.assertTrue(all(item["status"] == "interior_witness_found" for item in route["contact_witnesses"]))

    def test_noncontact_preserved(self):
        bone = trimesh.creation.box(extents=[2, 2, 2])
        tool = trimesh.creation.icosphere(subdivisions=1, radius=.1)
        tool.apply_translation([20, 0, 0])
        result = contact_witness(bone, tool)
        self.assertEqual(result["status"], "no_verified_interior_witness")

    def test_duplicate_and_outside_parameter_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for parameters in ((2.4, 2.4), (-1,), (float("nan"),)):
                with self.assertRaises(ValueError):
                    build(Path(temp)/"invalid", parameters=parameters)


if __name__ == "__main__":
    unittest.main()
