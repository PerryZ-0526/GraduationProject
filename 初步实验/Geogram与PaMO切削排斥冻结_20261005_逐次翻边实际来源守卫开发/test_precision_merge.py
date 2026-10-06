"""合并只接收完整同版本记录，保留失败分母。"""
import copy
import unittest
from merge_precision_resume import combine


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.original = {"routes": [{"id": name, "cutting_prefix_ids": ["e0"]} for name in ("旧", "新")]}
        self.remaining = {"routes": self.original["routes"][1:]}
        self.old = {"environment": {"precision_code_sha256": {"kernel.py": "fixed"},
                    "device": {"extension_sha256": "same", "gpu": "old"}},
                    "rows": [{"route": "旧", "event": "e0", "branch": branch, "status": "rejected"}
                             for branch in ("R", "full", "candidate")]}
        self.new = copy.deepcopy(self.old)
        self.new["status"] = "completed_with_recorded_failures"
        for row in self.new["rows"]:
            row.update(route="新", status="published_under_sampled_and_vertex_protocol")

    def test_failure_preserved(self):
        result = combine(self.original, self.remaining, self.old, self.new)
        self.assertEqual(result["total_events"], 2)
        self.assertEqual(result["complete_routes"]["candidate"], 1)
        self.assertEqual(result["status_counts"]["candidate"]["rejected"], 1)

    def test_running_rejected(self):
        self.new["status"] = "running"
        with self.assertRaises(ValueError):
            combine(self.original, self.remaining, self.old, self.new)

    def test_partial_rejected(self):
        self.new["rows"].pop()
        with self.assertRaises(ValueError):
            combine(self.original, self.remaining, self.old, self.new)

    def test_method_change_rejected(self):
        self.new["environment"]["precision_code_sha256"]["kernel.py"] = "changed"
        with self.assertRaises(ValueError):
            combine(self.original, self.remaining, self.old, self.new)

    def test_device_change_kept_separate(self):
        self.new["environment"]["device"]["gpu"] = "new"
        result = combine(self.original, self.remaining, self.old, self.new)
        self.assertEqual([device["gpu"] for device in result["devices"]], ["old", "new"])


if __name__ == "__main__":
    unittest.main()
