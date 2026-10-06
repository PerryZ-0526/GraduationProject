"""四因素诊断须保留原物理、拓扑和探针门槛，不混淆两个因素。"""
import ast
import unittest
from run_cleanup_order_ablation import variants


class CleanupAblationTests(unittest.TestCase):
    def test_four_declared_factor_combinations(self):
        sources = variants()
        self.assertEqual(set(sources), {'original', 'repair_before_guard', 'defer_encoding_guard', 'repair_and_defer'})
        for name, source in sources.items():
            ast.parse(source)
            repair = 'candidate, repaired_bits, repair = repair_physical_input' in source
            fp32_guard = 'if not valid or metrics["fp32_zero_area_faces"] or not topology:' in source
            self.assertEqual(repair, name in ('repair_before_guard', 'repair_and_defer'))
            self.assertEqual(fp32_guard, name in ('original', 'repair_before_guard'))

    def test_physical_topology_and_geometry_guards_remain(self):
        for source in variants().values():
            self.assertIn('mesh_valid_exact_contacts(candidate)', source)
            self.assertIn('candidate.euler_number==baseline.euler_number', source)
            self.assertIn('displacement>1e-7 or geometry["probe_max_mm"]>1e-7', source)
            self.assertIn('bits[keep]', source)
            self.assertIn('opposed_pairs', source)


if __name__ == '__main__':
    unittest.main()
