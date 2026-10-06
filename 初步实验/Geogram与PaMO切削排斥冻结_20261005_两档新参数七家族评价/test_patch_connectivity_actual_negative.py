"""实际连接与内部细分负例：保持旧点不等于同时满足嵌入和距离。"""

import hashlib
import json
from pathlib import Path
import unittest

import numpy as np
import trimesh


class ActualConnectivityNegativeTest(unittest.TestCase):
    def test_preserved_vertices_and_joint_rejection(self):
        root = Path(__file__).resolve().parents[1] / "可复用磨削测试集/局部连接与曲面投影联合负例_v23"
        record = json.loads((root / "01-局部连接与投影联合负例冻结.json").read_text("utf8"))
        for name, digest in record["files"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), digest)
        original = trimesh.load(root / "原连接提案.obj", force="mesh", process=False)
        final = trimesh.load(root / "翻边终态.obj", force="mesh", process=False)
        self.assertTrue(np.array_equal(original.vertices, final.vertices))
        self.assertFalse(np.array_equal(original.faces, final.faces))
        for row in record["rows"]:
            candidate = trimesh.load(root / row["file"], force="mesh", process=False)
            self.assertTrue(np.array_equal(candidate.vertices[:len(original.vertices)], original.vertices))
            self.assertFalse(row["checks"]["embedded_closed"] and row["geometry"]["probe_max_mm"] <= .1)
        # 包含嵌入通过但距离超差，以及距离通过但仍交叠两类真实反例。
        self.assertTrue(any(r["checks"]["embedded_closed"] for r in record["rows"]))
        self.assertTrue(any(r["geometry"]["probe_max_mm"] <= .1 for r in record["rows"]))
        self.assertFalse(record["tool_exclusion_certified"])


if __name__ == "__main__":
    unittest.main()
