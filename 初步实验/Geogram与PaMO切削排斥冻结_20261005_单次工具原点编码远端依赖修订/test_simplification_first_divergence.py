"""同输入首调用负例回归，防止把网格编号差异误当成形状差异。"""

import json
from pathlib import Path
import unittest

import trimesh

from audit_followup_candidate import sha256
from run_constrained_feedback import global_geometry


class FirstDivergenceTests(unittest.TestCase):
    def test_same_input_first_call_has_actual_geometry_difference(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/简化首调用同输入分歧_v14"
        record = json.loads((root / "01-首次简化分歧资产与证据.json").read_text("utf8"))
        for name, digest in record["files_sha256"].items():
            self.assertEqual(sha256(root / name), digest)
        first, second = record["first_calls"]
        self.assertEqual(first["input"], second["input"])
        self.assertEqual(first["num_faces_before"], second["num_faces_before"])
        self.assertNotEqual(first["num_faces_after"], second["num_faces_after"])
        # 重读保存对象复核几何差异，而非只依赖原记录摘要或面编号。
        meshes = [trimesh.load(root / name, force="mesh", process=False)
                  for name in ("首次简化输出一.obj", "首次简化输出二.obj")]
        actual = global_geometry(*meshes)
        self.assertGreater(actual["probe_max_mm"], .001)
        self.assertAlmostEqual(actual["probe_max_mm"], record["geometry"]["probe_max_mm"], places=9)


if __name__ == "__main__":
    unittest.main()
