"""保存复审新增锚点检查的源码结构与原父链几何门控保留。"""
import ast
from pathlib import Path
import unittest
from recheck_anchored_saved import build_anchor_recheck


class AnchoredSavedSourceTests(unittest.TestCase):
    def test_anchor_checks_and_original_acceptance_remain(self):
        original = Path(__file__).with_name("recheck_shared_feedback.py").read_text(encoding="utf-8")
        modified = build_anchor_recheck(original)
        ast.parse(modified)
        self.assertIn("np.array_equal(mesh.vertices[added], before.vertices[added])", modified)
        self.assertIn("passed = passed and anchor_ok", modified)
        self.assertNotIn("fixed_ok = fixed_ok and anchor_ok", modified)
        self.assertIn("fixed_added_anchors_exact=bool(anchor_ok)", modified)
        for condition in ("parent_ok = row[\"parent_sha256\"] == parent_sha", "cumulative_valid and cumulative[\"probe_max_mm\"] <= .1",
                          "actual_sha == row[\"output_sha256\"]", "np.array_equal(mesh.vertices[selected], source.vertices[ids[selected]])"):
            self.assertIn(condition, modified)

    def test_changed_structure_is_rejected(self):
        with self.assertRaises(ValueError):
            build_anchor_recheck("def recheck():\n    return True\n")


if __name__ == "__main__":
    unittest.main()
