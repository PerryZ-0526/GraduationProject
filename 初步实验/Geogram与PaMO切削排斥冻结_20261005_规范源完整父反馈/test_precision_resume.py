"""验证续跑分母保留失败记录，并拒绝重复、遗漏和半路线。"""
import copy
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from verify_precision_resume import partition, preflight


class ResumePartitionTests(unittest.TestCase):
    def setUp(self):
        self.original = {"routes": [{"id": name, "cutting_prefix_ids": ["e0", "e1"]}
                                     for name in ("已完成", "待执行")]}
        self.remaining = {"routes": [copy.deepcopy(self.original["routes"][1])]}
        self.rows = [{"route": "已完成", "event": event, "branch": branch, "status": "rejected"}
                     for event in ("e0", "e1") for branch in ("R", "full", "candidate")]

    def test_failure_kept(self):
        result = partition(self.original, self.remaining, self.rows)
        self.assertEqual(result["recorded_events"], 2)
        self.assertEqual(result["remaining_events"], 2)
        self.assertEqual(result["prior_status_counts"], {"rejected": 6})

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            partition(self.original, self.remaining, self.rows + self.rows[:1])

    def test_partial_route_rejected(self):
        with self.assertRaises(ValueError):
            partition(self.original, self.remaining, self.rows[:-1])

    def test_missing_and_overlapping_routes_rejected(self):
        for routes in ([], self.original["routes"]):
            with self.assertRaises(ValueError):
                partition(self.original, {"routes": routes}, self.rows)

    def test_modified_input_rejected(self):
        changed = copy.deepcopy(self.remaining)
        changed["routes"][0]["cutting_prefix_ids"] = ["e0"]
        with self.assertRaises(ValueError):
            partition(self.original, changed, self.rows)

    def test_preflight_calls_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            prepared = Path(temp)
            (prepared / "02-断连续跑协议.json").write_text("{}", encoding="utf-8")
            (prepared / "01-完整范围冻结清单.json").write_text(
                json.dumps({"routes": [{"split": "evaluation"}]}), encoding="utf-8")
            with patch("verify_precision_resume.verify", return_value={"checked": True}) as check:
                self.assertEqual(preflight(["--prepared", temp, "--split", "evaluation"], prepared),
                                 {"checked": True})
                check.assert_called_once_with(prepared, prepared)
            with self.assertRaises(ValueError):
                preflight(["--prepared", temp, "--split", "development"], prepared)


if __name__ == "__main__":
    unittest.main()
