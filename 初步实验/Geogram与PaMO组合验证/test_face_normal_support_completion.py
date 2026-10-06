"""真实拒绝面回归与伪造工具支撑的否定测试。"""

import json
from pathlib import Path
import unittest
import numpy as np
import trimesh
from face_normal_support_completion import complete_face_support, certify_tool_containment


class SupportCompletionTest(unittest.TestCase):
    def test_real_face_completed_without_vertex_move(self):
        root = Path("D:/GraduationProject_切削排斥证据")
        path = root / "20261005_倍率4薄壁三刀真实父反馈/薄壁_新参数1p4375_交叉_e1_candidate_boolean/candidate.obj"
        mesh = trimesh.load(path, force="mesh", process=False)
        vertices = mesh.vertices.copy()
        prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
        route = next(r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"] if r["id"].startswith("薄壁_"))
        item = next(t for t in route["prefix_tools"] if t["event_id"] == "e1")
        tool = trimesh.load(prepared / "inputs" / item["mesh"], force="mesh", process=False)
        _, _, _, certificate, details = complete_face_support(mesh, tool)
        self.assertTrue(certificate["passed"])
        self.assertEqual(details["initial_failed_faces"], 1)
        self.assertEqual(len(details["added_planes"]), 1)
        np.testing.assert_array_equal(vertices, mesh.vertices)

    def test_offset_cannot_exclude_tool_vertices(self):
        tool = trimesh.creation.box()
        self.assertFalse(certify_tool_containment(tool, [1., 0., 0.], np.nextafter(.5, -np.inf)))
        self.assertTrue(certify_tool_containment(tool, [1., 0., 0.], .5))
        self.assertFalse(certify_tool_containment(tool, [0., 0., 0.], 0.))

    def test_more_than_twenty_failed_faces_not_truncated(self):
        root = Path("D:/GraduationProject_切削排斥证据")
        mesh = trimesh.load(root / "20261005_倍率4薄壁三刀真实父反馈/薄壁_新参数1p4375_交叉_e1_candidate_boolean/candidate.obj", force="mesh", process=False)
        prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
        route = next(r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"] if r["id"].startswith("薄壁_"))
        item = next(t for t in route["prefix_tools"] if t["event_id"] == "e1")
        tool = trimesh.load(prepared / "inputs" / item["mesh"], force="mesh", process=False)
        # 重复面仅用于支撑子问题，检验失败面摘要20条上限，不是合法发布网格。
        repeated = trimesh.Trimesh(mesh.vertices, np.repeat(mesh.faces[[2336]], 35, axis=0), process=False)
        _, _, _, certificate, details = complete_face_support(repeated, tool)
        self.assertTrue(certificate["passed"])
        self.assertEqual(details["initial_failed_faces"], 35)
        self.assertEqual(details["tested_faces"], 35)

    def test_intersecting_triangle_not_certified(self):
        tool = trimesh.creation.box()
        mesh = trimesh.Trimesh([[-1., -1., 0.], [1., -1., 0.], [0., 1., 0.]], [[0, 1, 2]], process=False)
        _, _, _, certificate, _ = complete_face_support(mesh, tool)
        self.assertFalse(certificate["passed"])


if __name__ == "__main__":
    unittest.main()
