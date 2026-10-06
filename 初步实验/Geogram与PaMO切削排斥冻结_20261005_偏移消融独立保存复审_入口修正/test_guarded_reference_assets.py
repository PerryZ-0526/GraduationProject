"""验证冻结参照故障资产和实际十二步独立重放证据。"""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]/"可复用磨削测试集/CT独立参照中间输入失败及修复_v1"


def read(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))


class GuardedReferenceAssetTests(unittest.TestCase):
    def test_all_frozen_file_hashes(self):
        files = read("01-冻结清单.json")["files"]
        self.assertEqual(len(files), 11)
        for item in files:
            self.assertEqual(hashlib.sha256((ROOT/item["file"]).read_bytes()).hexdigest(), item["sha256"])

    def test_original_negative_and_repaired_operands(self):
        rows = read("07_01-全网格精确嵌入审计.json")["rows"]
        self.assertEqual([r["embedded_closed"] for r in rows], [False, True, True])
        for index, name in ((0, "01_raw_parent.obj"), (1, "04_repaired_parent_not_published.obj"), (2, "02_tool.obj")):
            self.assertEqual(rows[index]["sha256"], hashlib.sha256((ROOT/name).read_bytes()).hexdigest())

    def test_new_boolean_saved_result_bound(self):
        row = read("10_01-参照中间输入修复布尔诊断.json")
        self.assertEqual(row["execution"]["returncode"], 0)
        self.assertTrue(row["raw_result_valid"])
        cert = row["raw_result_metrics"]["full_exact_embedding"]
        self.assertTrue(cert["embedded_closed"])
        self.assertEqual(cert["saved_sha256"], hashlib.sha256((ROOT/"08_raw_result.obj").read_bytes()).hexdigest())

    def test_complete_independent_prefix(self):
        row = read("11_01-逐步参照完整前缀诊断.json")["record"]
        self.assertTrue(row["accepted"])
        self.assertEqual(row["tool_events"], ["e"+str(i) for i in range(12)])
        self.assertEqual(len(row["runs"]), 12)
        self.assertEqual(len(row["steps"]), 12)
        self.assertFalse(row["continuous_geometry_certified"])
        for step, run in zip(row["steps"], row["runs"]):
            self.assertEqual(run["returncode"], 0)
            self.assertTrue(step["accepted"])
            self.assertLessEqual(step["raw_to_repaired_geometry"]["probe_max_mm"], 1e-7)
            cert = step["validated_metrics"]["full_exact_embedding"]
            self.assertTrue(cert["embedded_closed"])
            self.assertEqual(cert["saved_sha256"], step["saved_sha256"])


if __name__ == "__main__":
    unittest.main()
