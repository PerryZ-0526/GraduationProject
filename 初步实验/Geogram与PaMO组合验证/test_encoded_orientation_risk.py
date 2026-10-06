"""编码方向风险的实际正面积反向负例及正常/塌缩控制。"""
import json
from pathlib import Path
import unittest
import numpy as np
from encoded_orientation_fragment_preparation import encoded_orientation_risk
from native_fp32_fragment_guard import native_fp32_invalid_faces


class EncodedOrientationRiskTests(unittest.TestCase):
    def test_positive_area_reversed_face_missed_by_area_detector(self):
        fixture = json.loads((Path(__file__).parent / '编码方向风险回归夹具/01-编码正面积反向面回归夹具.json').read_text('utf8'))
        v = np.asarray(fixture['triangle_world'], np.float64)
        faces = np.asarray([[0, 1, 2]])
        origin = np.asarray(fixture['origin_mm'])
        physical_normal = np.cross(v[1] - v[0], v[2] - v[0])
        local = (v - origin).astype(np.float32).astype(np.float64)
        encoded_normal = np.cross(local[1] - local[0], local[2] - local[0])
        # 负例在两种表示中都有正面积，不能用零面积面删除掩盖方向错误。
        self.assertGreater(np.linalg.norm(physical_normal), 2e-12)
        self.assertGreater(np.linalg.norm(encoded_normal), 2e-12)
        self.assertLess(float(physical_normal @ encoded_normal), 0.)
        self.assertFalse(native_fp32_invalid_faces(v, faces)[0])
        self.assertTrue(encoded_orientation_risk(v, faces, origin)[0])

    def test_regular_triangle_preserved(self):
        v = np.asarray([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
        self.assertFalse(encoded_orientation_risk(v, np.asarray([[0, 1, 2]]), np.zeros(3))[0])

    def test_collapsed_encoding_still_flagged(self):
        v = np.asarray([[1e8, 0., 0.], [1e8 + 1., 0., 0.], [1e8, 1., 0.]])
        # 新检测继续保留既有编码塌缩报警，不以方向规则取代面积规则。
        self.assertTrue(encoded_orientation_risk(v, np.asarray([[0, 1, 2]]), np.zeros(3))[0])


if __name__ == '__main__':
    unittest.main()
