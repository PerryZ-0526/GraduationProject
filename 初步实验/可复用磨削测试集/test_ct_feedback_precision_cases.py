"""两实际父反馈事件的精度回归，验证已发布帧而不缩小原138段分母。"""
import json
import hashlib
from pathlib import Path
import sys
import unittest
import numpy as np
import trimesh
sys.path.insert(0,str(Path(__file__).parents[1]/"Geogram与PaMO组合验证"))
from preserved_saved_binding import mesh_valid_saved_binding
from preserved_geometry_precondition import require_fixed_degenerate_faces

ROOT = Path(__file__).parent/"CT第六第七事件真实反馈回归_v1"


def read(event,name):
    return json.loads((ROOT/"inputs"/event/name).read_text(encoding="utf-8"))


class CTFeedbackPrecisionTests(unittest.TestCase):
    def test_all_frozen_files(self):
        manifest = json.loads((ROOT/"01-CT真实反馈两事件清单.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["whole_138_completed"])
        self.assertEqual(len(manifest["files"]),18)
        for row in manifest["files"]:
            raw = (ROOT/row["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row["sha256"])
            self.assertEqual(len(raw),row["bytes"])

    def test_actual_parent_chain(self):
        for event in ("e5","e6"):
            row = read(event,"case.json")["row"]
            folder = ROOT/"inputs"/event
            self.assertEqual(hashlib.sha256((folder/"parent.obj").read_bytes()).hexdigest(),row["parent_sha256"])
            self.assertEqual(hashlib.sha256((folder/"candidate.obj").read_bytes()).hexdigest(),row["output_sha256"])
            self.assertEqual(row["status"],"published_under_sampled_and_vertex_protocol")
        self.assertEqual(read("e5","case.json")["row"]["output_sha256"],read("e6","case.json")["row"]["parent_sha256"])

    def test_input_count_and_full_finite_trace(self):
        for event,expected in (("e5",6),("e6",10)):
            row = read(event,"case.json")["row"]
            self.assertEqual(row["input_metrics"]["fp32_zero_area_faces"],expected)
            attempt = next(a for a in row["attempts"] if a["status"] == "accepted_sampled")
            self.assertTrue(attempt["numerical_diagnostic"]["passed"])
            self.assertTrue(attempt["fixed_geometry_arithmetic_precondition"]["all_degenerate_vertices_fixed"])
            trace = read(event,"diff_trace.json")["rows"]
            self.assertEqual(len(trace),50)
            self.assertTrue(all(x["full_energy_finite"] and x["finite_positions"] and not x["nonfinite_free_vertices"] for x in trace))

    def test_source_and_candidate_embedding_and_fixed_points(self):
        for event in ("e5","e6"):
            root = ROOT/"inputs"/event
            row = read(event,"case.json")["row"]
            source,candidate = [trimesh.load(root/name,process=False) for name in ("source.obj","candidate.obj")]
            attempt = next(a for a in row["attempts"] if a["status"] == "accepted_sampled")
            for mesh,metrics in ((source,row["input_metrics"]),(candidate,attempt["output_metrics"])):
                certificate = metrics["full_exact_embedding"]
                self.assertTrue(mesh_valid_saved_binding(mesh,{certificate["saved_sha256"]:certificate})[0])
            ids = np.asarray(attempt["vertex_original_ids"])
            selected = ids >= 0
            np.testing.assert_array_equal(candidate.vertices[selected],source.vertices[ids[selected]])
            scale = 1.0/np.ptp(source.vertices,axis=0).max()
            result = require_fixed_degenerate_faces(candidate.vertices,candidate.faces,selected,scale,-source.vertices.mean(axis=0)*scale)
            self.assertTrue(result["all_degenerate_vertices_fixed"])

    def test_actual_independent_reference_binding(self):
        manifest = json.loads((ROOT.parent/"真实CT既有两路线输入_v1/01-完整范围冻结清单.json").read_text(encoding="utf-8"))
        route = next(row for row in manifest["routes"] if row["id"] == "application_ct_original138")
        for event in ("e5","e6"):
            case = read(event,"case.json")
            false = case["reference_loading"] == "process_false"
            reference = trimesh.load(ROOT/"inputs"/event/"reference.obj",process=not false,validate=not false)
            certificate = case["reference_row"]["metrics"]["full_exact_embedding"]
            self.assertTrue(mesh_valid_saved_binding(reference,{certificate["saved_sha256"]:certificate})[0])
            recovery = case["reference_row"]["recovery"]
            self.assertEqual(recovery["initial_sha256"],route["initial_mesh_sha256"])
            through = int(event[1:])+1
            self.assertEqual(recovery["tool_events"],["e"+str(i) for i in range(through)])
            self.assertEqual(recovery["tool_sha256"],[row["sha256"] for row in route["prefix_tools"][:through]])


if __name__ == "__main__":
    unittest.main()
