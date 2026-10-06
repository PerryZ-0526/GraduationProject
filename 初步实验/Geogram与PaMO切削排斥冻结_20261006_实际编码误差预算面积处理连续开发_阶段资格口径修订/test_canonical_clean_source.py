"""真实来源资产的排列不变性及有向面、来源关联回归。"""

import json
from pathlib import Path
import unittest

import numpy as np
import trimesh
from canonical_clean_source import canonical_clean_source


class CanonicalSourceTest(unittest.TestCase):
    def test_feedback_cleanup_keeps_original_face_association(self):
        from run_canonical_stepwise_feedback import canonical_cleanup
        root = Path(r"D:\GraduationProject_切削排斥证据\可复用磨削测试集\布尔源排列同几何分歧_v24")
        mesh = trimesh.load(root / "原始_0_clean_source.obj", force="mesh", process=False)
        bits = np.asarray(json.loads((root / "原始_0_clean_labels.json").read_text("utf8"))["operand_bits"])
        canonical, labels, details = canonical_cleanup(mesh, bits, allow_shared=True)
        # 检查进入真实反馈入口的原面号仍对应同向三角形与原来源标签。
        for new_id, original_id in enumerate(details["surviving_original_face_ids"]):
            actual = canonical.vertices[canonical.faces[new_id]]
            expected = mesh.vertices[mesh.faces[original_id]]
            self.assertTrue(any(np.allclose(actual, np.roll(expected, shift, axis=0), rtol=0, atol=1e-7) for shift in range(3)))
            self.assertEqual(labels[new_id], bits[original_id])

    def test_actual_pair_and_reindexed_source(self):
        root = Path(r"D:\GraduationProject_切削排斥证据\可复用磨削测试集\布尔源排列同几何分歧_v24")
        results = []
        for index in range(2):
            mesh = trimesh.load(root / f"原始_{index}_clean_source.obj", force="mesh", process=False)
            bits = np.asarray(json.loads((root / f"原始_{index}_clean_labels.json").read_text("utf8"))["operand_bits"])
            canonical, labels, proof = canonical_clean_source(mesh, bits)
            # 逐面恢复原来的有向坐标和来源，避免排序错误被两份同源输出掩盖。
            for new_id, old_id in enumerate(proof["old_face_ids"]):
                start = proof["cyclic_start_by_old_face"][old_id]
                expected = np.roll(mesh.vertices[mesh.faces[old_id]], -start, axis=0)
                np.testing.assert_array_equal(canonical.vertices[canonical.faces[new_id]], expected)
                self.assertEqual(labels[new_id], bits[old_id])
            results.append((canonical, labels))
            # 固定随机排列顶点和面，并循环改变面起点，不反转绕序。
            rng = np.random.default_rng(20261005)
            vertices = rng.permutation(len(mesh.vertices))
            inverse = np.argsort(vertices)
            faces = rng.permutation(len(mesh.faces))
            reordered = trimesh.Trimesh(mesh.vertices[vertices], np.roll(inverse[mesh.faces[faces]], 1, axis=1), process=False)
            repeated, repeated_labels, _ = canonical_clean_source(reordered, bits[faces])
            np.testing.assert_array_equal(canonical.vertices, repeated.vertices)
            np.testing.assert_array_equal(canonical.faces, repeated.faces)
            np.testing.assert_array_equal(labels, repeated_labels)
        np.testing.assert_array_equal(results[0][0].vertices, results[1][0].vertices)
        np.testing.assert_array_equal(results[0][0].faces, results[1][0].faces)
        np.testing.assert_array_equal(results[0][1], results[1][1])


if __name__ == "__main__":
    unittest.main()
