"""子路线复审必须完整，不得将整批运行状态改成完成。"""
import unittest
from recheck_completed_preserved_route import require_complete_route


class CompletedRouteTests(unittest.TestCase):
    def setUp(self):
        self.route = dict(id="r", cutting_prefix_ids=["e0", "e1"])
        self.report = dict(status="running", rows=[dict(route="r", event=e, branch=b,
            status="reference_valid" if b == "R" else "published_under_sampled_and_vertex_protocol")
            for e in self.route["cutting_prefix_ids"] for b in ("R", "full", "candidate")])

    def test_complete_route_keeps_full_batch_running(self):
        self.assertEqual(len(require_complete_route(self.report, self.route)), 6)
        self.assertEqual(self.report["status"], "running")

    def test_missing_or_duplicate_records_rejected(self):
        original = self.report["rows"]
        for rows in (original[:-1], original+[original[-1]], original[:-1]+[original[0]]):
            self.report["rows"] = rows
            with self.assertRaises(ValueError):
                require_complete_route(self.report, self.route)

    def test_pending_unknown_or_missing_status_rejected(self):
        for state in ("running", "pending", "", "unknown", None):
            self.report["rows"][0]["status"] = state
            with self.assertRaises(ValueError):
                require_complete_route(self.report, self.route)

    def test_other_route_cannot_fill_missing_record(self):
        self.report["rows"][-1]["route"] = "other"
        with self.assertRaises(ValueError):
            require_complete_route(self.report, self.route)


if __name__ == "__main__":
    unittest.main()
