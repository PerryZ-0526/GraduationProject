"""原固定接触分支必须保留作者动态核体，不能扩展到含自由点的接触。"""
import ast
from pathlib import Path
import unittest
from preserved_collision_source import preserve_energy_source, preserve_ccd_source, ALL_FIXED

AUTHOR = Path(__file__).parents[2]/"reference/近期强基线_20260908/pamo/simp_cuda/safe_project/src/pamo_safe_project/kernels"


class PreservedSourceTests(unittest.TestCase):
    def verify_bodies(self, relative, transform, names):
        source = (AUTHOR/relative).read_text(encoding="utf-8")
        original = {node.name: node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
        changed = {node.name: node for node in ast.parse(transform(source)).body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(set(original),set(changed))
        for name in original:
            body = changed[name].body
            if name in names:
                inserted = [node for node in body if isinstance(node,ast.If) and "original_fixed" in ast.unparse(node.test)]
                self.assertEqual(len(inserted),1)
                body = [node for node in body if node is not inserted[0]]
                self.assertEqual([arg.arg for arg in changed[name].args.args[-4:]],
                                 ["original_fixed","original_mm","geometry_scale","geometry_failures"])
            self.assertEqual([ast.dump(node) for node in body],[ast.dump(node) for node in original[name].body],name)

    def test_energy_dynamic_bodies_unchanged(self):
        self.verify_bodies("energy_kernels/collision_energy.py",preserve_energy_source,
                           {"collision_energy_kernel","collision_diff_kernel","collision_hess_dx_kernel"})

    def test_ccd_dynamic_body_unchanged(self):
        self.verify_bodies("ccd_kernels.py",preserve_ccd_source,{"accd_kernel"})

    def test_fixed_predicate_requires_all_four(self):
        tree = ast.parse(ALL_FIXED,mode="eval").body
        self.assertIsInstance(tree,ast.BoolOp)
        self.assertIsInstance(tree.op,ast.And)
        self.assertEqual(len(tree.values),4)
        self.assertEqual([node.left.slice.slice.elts[1].value for node in tree.values],[0,1,2,3])

    def test_missing_author_signature_rejected(self):
        with self.assertRaises(ValueError):
            preserve_energy_source("x=1\n")


if __name__ == "__main__":
    unittest.main()
