"""精确嵌入审计绑定真实发布对象，运行中或被改写的网格必须拒绝。"""
import json
from pathlib import Path
import tempfile
import unittest
from audit_cut_embedding import published_paths
from audit_followup_candidate import sha256


class PublishedScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        folder = self.root / "route_e0_candidate_boolean"
        folder.mkdir()
        self.mesh = folder / "candidate.obj"
        self.mesh.write_text("v 0 0 0\n", encoding="utf-8")
        self.row = dict(route="route", event="e0", branch="candidate", selected_method="boolean",
                        status="published_under_sampled_and_vertex_protocol", output_sha256=sha256(self.mesh))
        self.record = self.root / "record.json"

    def write_record(self, status="completed_with_recorded_failures", rows=None):
        self.record.write_text(json.dumps(dict(status=status, rows=rows or [self.row])), encoding="utf-8")

    def test_saved_publication_bound(self):
        self.write_record()
        paths, bindings = published_paths([self.record])
        self.assertEqual(paths, [self.mesh])
        self.assertEqual(bindings[0]["record_sha256"], sha256(self.record))
        self.assertEqual(bindings[0]["saved_sha256"], sha256(self.mesh))

    def test_running_rejected(self):
        self.write_record(status="running")
        with self.assertRaises(ValueError):
            published_paths([self.record])

    def test_changed_mesh_rejected(self):
        self.write_record()
        self.mesh.write_text("v 1 0 0\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            published_paths([self.record])

    def test_reuse_and_reference_not_new_outputs(self):
        reuse = dict(self.row, event="e1", status="contained_reused_parent")
        reference = dict(self.row, branch="R", event="e2", status="reference_valid")
        self.write_record(rows=[self.row, reuse, reference])
        self.assertEqual(len(published_paths([self.record])[0]), 1)

    def test_duplicate_record_rejected(self):
        self.write_record()
        with self.assertRaises(ValueError):
            published_paths([self.record, self.record])


if __name__ == "__main__":
    unittest.main()
