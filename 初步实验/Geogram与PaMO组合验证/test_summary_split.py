"""长序列统计分母须与执行器split一致，不能把其他阶段补算或隐去。"""
import unittest
from summarize_shared_feedback import selected_routes


class SummarySplitTests(unittest.TestCase):
    def test_full_executed_split_preserved(self):
        routes=[dict(id='a',split='long',cutting_prefix_ids=['e0','e1']),
                dict(id='b',split='long',cutting_prefix_ids=['e0']),
                dict(id='c',split='evaluation',cutting_prefix_ids=['e0','e1','e2'])]
        self.assertEqual(selected_routes(routes,'long'),routes[:2])
        self.assertEqual(sum(len(r['cutting_prefix_ids']) for r in selected_routes(routes,'long')),3)

    def test_unknown_split_rejected(self):
        with self.assertRaisesRegex(ValueError,'没有路线'):
            selected_routes([dict(split='long')],'unknown')


if __name__=='__main__':
    unittest.main()
