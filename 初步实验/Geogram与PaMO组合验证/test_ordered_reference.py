"""参照修复只改变物理清理顺序，保留原初态与工具数据独立。"""
import ast
import unittest
from run_ordered_reference_feedback import reference_source
from run_physical_geometry_feedback import build_entry
from run_constrained_batch import HERE


class OrderedReferenceTests(unittest.TestCase):
    def test_only_cleanup_import_changes(self):
        original=(HERE/'guarded_reference_recovery.py').read_text(encoding='utf-8')
        expected=original.replace('from opposed_facet_cleanup import clean_cancel_opposed',
            'from ordered_physical_cleanup import ordered_cancel_opposed as clean_cancel_opposed')
        source=reference_source()
        self.assertEqual(source,expected)
        ast.parse(source)

    def test_original_initial_and_tools_still_verified(self):
        source=reference_source()
        for fragment in ('prefix_tools_through(route, event)','sha256(initial) != route["initial_mesh_sha256"]',
            'sha256(source) != tool["sha256"]','geometry["probe_max_mm"] <= 1e-7',
            'check_preserved_mesh(engine, step/"checks"','仅原初态与截至事件原工具'):
            self.assertIn(fragment,source)
        self.assertNotIn('candidate.obj',source)

    def test_generated_reference_keeps_physical_and_publication_checks(self):
        entry=build_entry((HERE/'run_preserved_geometry_feedback.py').read_text(encoding='utf-8'),reference_source())
        ast.parse(entry)
        self.assertIn('from physical_input_repair import repair_physical_input as repair_preserved_input',entry)
        self.assertIn('ordered_cancel_opposed as clean_cancel_opposed',entry)
        self.assertIn('check_preserved_mesh',entry)


if __name__=='__main__':
    unittest.main()
