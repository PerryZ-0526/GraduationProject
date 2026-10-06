"""真实局部回退回归：不移动无关点，嵌入恢复仍不能冒称几何通过。"""

import hashlib
import json
from pathlib import Path
import unittest

import numpy as np
import trimesh


class ActualLocalBackoffTest(unittest.TestCase):
    def test_actual_locality_and_retained_failures(self):
        root = Path(__file__).resolve().parents[1] / "可复用磨削测试集/局部碰撞回退成败对照_v22"
        manifest = json.loads((root / "01-局部碰撞回退完整负例冻结.json").read_text("utf8"))
        for name, expected in manifest["files"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected)
        rows = manifest["rows"]
        self.assertEqual(len(rows), 6)
        original = trimesh.load(root / rows[0]["file"], force="mesh", process=False)
        half = trimesh.load(root / rows[1]["file"], force="mesh", process=False)
        affected = rows[1]["backoff_vertices"]
        self.assertEqual(len(affected), 6)
        unchanged = np.ones(len(original.vertices), dtype=bool)
        unchanged[affected] = False
        self.assertTrue(np.array_equal(original.faces, half.faces))
        self.assertTrue(np.array_equal(original.vertices[unchanged], half.vertices[unchanged]))
        self.assertGreater(float(np.linalg.norm(original.vertices[affected] - half.vertices[affected], axis=1).max()), 0)
        self.assertFalse(rows[0]["embedded_closed"])
        self.assertTrue(rows[1]["embedded_closed"])
        self.assertGreater(rows[1]["probe_max_mm"], .1)
        # 保存的六提案没有同时通过两项，工具排斥也尚未认证。
        self.assertFalse(any(r["embedded_closed"] and r["probe_max_mm"] <= .1 for r in rows))
        self.assertFalse(manifest["tool_exclusion_certified"])


if __name__ == "__main__":
    unittest.main()
