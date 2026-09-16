"""先用集合成员与解析反例验证表达，不以相同公式自我对拍。"""
import unittest
import numpy as np
from target import cut_field, update_field, box_field


def membership(points, item):
    """用轴向端点分区和叉积距离独立判断胶囊成员。"""
    a, b = np.array(item['start']), np.array(item['end'])
    axis = b-a
    length = np.linalg.norm(axis)
    v = points-a
    if length == 0:
        distance = np.linalg.norm(v, axis=1)
    else:
        unit = axis/length
        height = v @ unit
        distance = np.linalg.norm(np.cross(v, unit), axis=1)
        distance = np.where(height < 0, np.linalg.norm(v, axis=1), distance)
        distance = np.where(height > length, np.linalg.norm(points-b, axis=1), distance)
    return ((distance < item['radius']) &
            (np.linalg.norm(points[:, :2], axis=1) < item['clip_radius']) &
            (np.abs(points[:, 2]) < 20))


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.points = np.random.default_rng(20260908).uniform(-5, 5, (20000, 3))
        self.tool = dict(start=[-2, 0, -1], end=[2, 1, 3], radius=2., clip_radius=2.5)

    def test_oblique_and_vertical(self):
        for end in ([2, 1, 3], [-2, 0, 4], [-2, 0, -1]):
            tool = dict(self.tool, end=end)
            np.testing.assert_array_equal(cut_field(self.points, tool) < 0, membership(self.points, tool))

    def test_clip_and_caps(self):
        tool = dict(start=[0, 0, -30], end=[0, 0, 30], radius=3., clip_radius=2.)
        np.testing.assert_array_equal(cut_field([[0, 0, 0], [2.5, 0, 0], [0, 0, 21]], tool) < 0,
                                      [True, False, False])

    def test_repeat_and_order(self):
        p = self.points
        base = box_field(p, [4, 4, 4])
        other = dict(self.tool, start=[1, -3, 2], end=[0, 4, -1])
        once = update_field(base, p, self.tool)
        np.testing.assert_array_equal(once, update_field(once, p, self.tool))
        np.testing.assert_array_equal(update_field(once, p, other),
            update_field(update_field(base, p, other), p, self.tool))
        self.assertTrue(np.all(once >= base))

    def test_subdivision(self):
        midpoint = (np.array(self.tool['start'])+self.tool['end'])/2
        split = np.minimum(cut_field(self.points, dict(self.tool, end=midpoint)),
                           cut_field(self.points, dict(self.tool, start=midpoint)))
        np.testing.assert_allclose(split, cut_field(self.points, self.tool), atol=2e-15, rtol=0)

    def test_zero_set_is_not_material_boundary(self):
        # 相同实体相减后没有内部，但max(f,-f)仍可能为零；禁止把全部零点当有效骨面。
        tool = dict(start=[0, 0, 0], end=[0, 0, 0], radius=1., clip_radius=3.)
        points = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0.]])
        field = update_field(cut_field(points, tool), points, tool)
        self.assertFalse(np.any(field < 0))
        self.assertEqual(field[1], 0)


if __name__ == '__main__':
    unittest.main()
