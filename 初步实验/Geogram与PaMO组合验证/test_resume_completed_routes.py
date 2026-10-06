"""恢复仅允许完整路线和同摘要实际发布对象。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from resume_completed_routes import completed_routes
from audit_followup_candidate import sha256


class CompletedRouteResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.output=Path(self.temp.name)
        self.route=dict(id='路线',cutting_prefix_ids=['e0'])
        self.manifest=dict(routes=[self.route])
        (self.output/'input_manifest.json').write_text(json.dumps(self.manifest),encoding='utf-8')
        self.rows=[dict(route='路线',event='e0',branch=b,status='blocked_by_previous_failure') for b in ('R','full','candidate')]
        self.report=dict(manifest_sha256=sha256(self.output/'input_manifest.json'),rows=self.rows,route_event_policy={'路线':{}})

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_route_retained(self):
        self.assertEqual(completed_routes(self.report,self.manifest,self.output),['路线'])

    def test_partial_route_rejected(self):
        self.rows.pop()
        with self.assertRaises(ValueError):completed_routes(self.report,self.manifest,self.output)

    def test_unregistered_artifact_rejected(self):
        self.report['rows']=[]
        (self.output/'路线_e0_reference').mkdir()
        with self.assertRaises(ValueError):completed_routes(self.report,self.manifest,self.output)

    def test_changed_published_output_rejected(self):
        row=self.rows[-1];row.update(status='published_under_sampled_and_vertex_protocol',selected_method='boolean',output_sha256='invalid')
        folder=self.output/'路线_e0_candidate_boolean';folder.mkdir();(folder/'candidate.obj').write_bytes(b'object')
        with self.assertRaises(ValueError):completed_routes(self.report,self.manifest,self.output)


if __name__=='__main__':
    unittest.main()
