"""子路线复审必须完整，不得将整批运行状态改成完成。"""
import unittest
import json
from pathlib import Path
import runpy
import sys
import tempfile
from unittest.mock import patch
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

    def test_incomplete_actual_entry_does_not_reserve_snapshot_path(self):
        import recheck_completed_preserved_route as entry
        from audit_followup_candidate import sha256
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);prepared=root/'prepared';prepared.mkdir();output=root/'output';output.mkdir()
            manifest=prepared/'01-完整范围冻结清单.json'
            manifest.write_text(json.dumps(dict(routes=[self.route])),encoding='utf-8')
            report=dict(self.report,manifest_sha256=sha256(manifest),rows=self.report['rows'][:-1])
            (output/'01-反馈执行与独立审计.json').write_text(json.dumps(report),encoding='utf-8')
            arguments=[entry.__file__,'--prepared',str(prepared),'--output',str(output),'--route','r','--port','1']
            # 实际main应在构造SSH引擎和快照写入之前拒绝不完整子路线。
            with patch.object(sys,'argv',arguments),self.assertRaisesRegex(ValueError,'未完整'):
                runpy.run_path(entry.__file__,run_name='__main__')
            self.assertFalse((output/'09-r-复审记录快照.json').exists())
            self.assertFalse((output/'frozen_snapshot_write.py').exists())


if __name__ == "__main__":
    unittest.main()
