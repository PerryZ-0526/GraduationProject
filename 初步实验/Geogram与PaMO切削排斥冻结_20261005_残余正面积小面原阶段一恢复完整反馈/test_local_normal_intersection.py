"""真实负例回归：正面积及局部法向不反转不能替代全量嵌入检查。"""

import json
from pathlib import Path
import unittest

import numpy as np
import trimesh

from audit_followup_candidate import sha256
from exact_embedding_gate import mesh_valid_full_embedding


class NormalIntersectionTests(unittest.TestCase):
    def test_positive_normals_and_areas_still_fail_embedding(self):
        root = Path(__file__).parents[1] / "可复用磨削测试集/局部法向保持仍自交_v19"
        record = json.loads((root / "01-局部法向保持与全量自交负例.json").read_text("utf8"))
        for name, digest in record["files_sha256"].items():
            self.assertEqual(sha256(root / name), digest)
        base = trimesh.load(root / "合法恢复基准.obj", force="mesh", process=False)
        bad = trimesh.load(root / "失败QP实际对象.obj", force="mesh", process=False)
        proof = record["diagnosis"]["rows"][1]
        self.assertEqual(proof["saved_sha256"], sha256(root / "失败QP实际对象.obj"))
        self.assertEqual(proof["checks"]["self_intersection_pairs"], 3)
        self.assertFalse(proof["checks"]["embedded_closed"])
        ids = sorted({i for pair in proof["checks"]["intersection_face_ids"] for i in pair})
        parents = np.asarray(record["refinement"]["parent_face_ids"])
        products = np.einsum("ij,ij->i", base.face_normals[parents[ids]], bad.face_normals[ids])
        self.assertTrue(np.all(products > 0))
        self.assertTrue(np.all(bad.area_faces[ids] > 0))
        self.assertTrue(bad.is_watertight)
        # 同摘要完整否定证据必须保留拒绝，局部正常不能覆盖它。
        certificate = {**proof["checks"], "saved_mesh_sha256": proof["saved_sha256"]}
        self.assertFalse(mesh_valid_full_embedding(bad, certificate)[0])


if __name__ == "__main__":
    unittest.main()
