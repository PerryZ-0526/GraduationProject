"""结果映射测试：拒绝、缺失证书及局部状态身份不能被界面掩盖。"""
import unittest
from research_results import EXPERIMENTS, series_from_file


class ResultTests(unittest.TestCase):
    def test_rejection_has_no_snapshot(self):
        runs = dict(series_from_file(EXPERIMENTS/'CUDA真实骨面对照/轨迹覆盖结果/20260908_131332/results.json'))
        row = runs['真实局部 / shift_x_1 / cuda'][-1]
        self.assertFalse(row['accepted'])
        self.assertIsNone(row['snapshot'])
        self.assertEqual(runs['真实局部 / control / cuda'][-1]['snapshot'], 16)

    def test_baseline_has_no_certificate(self):
        runs = series_from_file(EXPERIMENTS/'CUDA真实骨面对照/强基线覆盖结果/20260908_132411/results.json')
        self.assertIsNone(runs[0][1][0]['error_bound_mm'])
        self.assertTrue(runs[0][1][-1]['mesh'].exists())

    def test_analytic_is_not_bone(self):
        runs = series_from_file(EXPERIMENTS/'三维目标几何机制/实验结果/20260908_135848/results.json')
        self.assertEqual(sum(len(rows) for _, rows in runs), 8)
        self.assertTrue(all(name.startswith('解析') for name, _ in runs))


if __name__ == '__main__':
    unittest.main()
