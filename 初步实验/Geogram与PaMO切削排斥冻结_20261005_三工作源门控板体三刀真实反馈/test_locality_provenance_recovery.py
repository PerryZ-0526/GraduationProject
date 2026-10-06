"""来源恢复只能使用操作数几何，双匹配与错误既有标签必须拒绝。"""

import unittest
import numpy as np
import trimesh

from locality_provenance_recovery import recover_sources


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.parent = trimesh.creation.box()
        self.tool = self.parent.copy()
        self.tool.apply_translation([3, 0, 0])

    def test_missing_parent_labels_recovered(self):
        labels, record = recover_sources(self.parent, np.zeros(len(self.parent.faces)), self.parent, self.tool)
        np.testing.assert_array_equal(labels, np.ones(len(self.parent.faces)))
        self.assertEqual(record["uniquely_recovered_faces"], len(self.parent.faces))

    def test_double_match_rejected(self):
        with self.assertRaisesRegex(ValueError, "双匹配"):
            recover_sources(self.parent, np.zeros(len(self.parent.faces)), self.parent, self.parent)

    def test_unmatched_source_rejected(self):
        mesh = self.parent.copy()
        mesh.apply_translation([0, 3, 0])
        with self.assertRaisesRegex(ValueError, "无匹配"):
            recover_sources(mesh, np.zeros(len(mesh.faces)), self.parent, self.tool)

    def test_wrong_known_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "已有来源"):
            recover_sources(self.parent, np.full(len(self.parent.faces), 2), self.parent, self.tool)


if __name__ == "__main__":
    unittest.main()
