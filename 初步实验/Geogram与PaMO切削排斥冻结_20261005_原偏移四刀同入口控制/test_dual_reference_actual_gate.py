"""真实第四刀回归：累计参照通过不能代替维护源通过。"""

import hashlib
import json
from pathlib import Path
import unittest

import trimesh
import run_reference_cut_feedback
from dual_reference_coverage_exclusion import dual_reference_geometry


class ActualDualReferenceTest(unittest.TestCase):
    def test_same_raw_input_recovery_preserves_both_budgets(self):
        root = Path(__file__).resolve().parents[1] / "可复用磨削测试集/双参照提前停止真实成败对照_v20"
        manifest = json.loads((root / "01-双参照真实成败冻结清单.json").read_text("utf8"))
        repaired = json.loads((root / "03-同输入双参照恢复静态证明.json").read_text("utf8"))
        path = root / repaired["candidate_file"]
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), repaired["candidate_sha256"])
        row = manifest["rows"][0]
        # 新候选仍对照旧拒绝例的同一维护源和累计参照，不换参照解释成功。
        meshes = {role: trimesh.load(root / item["file"], force="mesh", process=(role == "cumulative_reference"))
                  for role, item in row["files"].items()}
        geometry = dual_reference_geometry(trimesh.load(path, force="mesh", process=False),
            meshes["cumulative_reference"], meshes["maintenance_source"])
        self.assertLessEqual(geometry["worst_probe_max_mm"], .1)
        self.assertAlmostEqual(geometry["worst_probe_max_mm"], repaired["proof"]["geometry"]["worst_probe_max_mm"], places=8)
        self.assertEqual(repaired["proof"]["exact_embedding"]["saved_sha256"], repaired["candidate_sha256"])
        self.assertTrue(repaired["proof"]["exact_embedding"]["embedded_closed"])
        self.assertEqual(repaired["proof"]["new_GPU_calls"], 0)

    def test_actual_rejected_and_published_fourth_cuts(self):
        root = Path(__file__).resolve().parents[1] / "可复用磨削测试集/双参照提前停止真实成败对照_v20"
        manifest = json.loads((root / "01-双参照真实成败冻结清单.json").read_text("utf8"))
        for row in manifest["rows"]:
            with self.subTest(label=row["label"]):
                meshes = {}
                for role, item in row["files"].items():
                    path = root / item["file"]
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
                    meshes[role] = trimesh.load(path, force="mesh", process=(role == "cumulative_reference"))
                geometry = dual_reference_geometry(meshes["candidate"], meshes["cumulative_reference"], meshes["maintenance_source"])
                self.assertAlmostEqual(geometry["cumulative"]["probe_max_mm"], row["expected_cumulative_mm"], places=8)
                self.assertAlmostEqual(geometry["maintenance_source"]["probe_max_mm"], row["expected_source_mm"], places=8)
                # 两例累计参照都通过；旧例必须因维护源超差拒绝，真实发布例两项都通过。
                self.assertLessEqual(geometry["cumulative"]["probe_max_mm"], .1)
                self.assertEqual(geometry["worst_probe_max_mm"] <= .1, row["status"] == "published")


if __name__ == "__main__":
    unittest.main()
