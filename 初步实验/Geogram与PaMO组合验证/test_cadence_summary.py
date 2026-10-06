"""防止将失败短路线或设备污染误算为完整路线速度收益。"""
import unittest
from summarize_cadence_results import compare


def row(policy,complete=True,contaminated=False,cost=100):
    return dict(route='route',round=0,policy=policy,complete=complete,gpu_other_process_observed=contaminated,
        total_execution_ms=cost,maintenance_calls=4,p95_ms=50,final_quality={},published=4 if complete else 1,
        planned=4,status_counts={'published':4} if complete else {'published':1,'candidate_audit_rejected':1,'blocked_by_previous_failure':2},
        maximum_published_angle10_fraction=0.1,maximum_published_angle10_area_fraction=0.01,
        mandatory_repairs=0,final_flushes=1)


class SummaryTests(unittest.TestCase):
    def test_only_complete_pairs_count(self):
        _,pairs=compare([row('every'),row('period2',cost=50),row('period4',complete=False,cost=10)])
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0]['policy'],'period2')
        self.assertEqual(pairs[0]['speedup'],2)

    def test_contamination_and_incomplete_baseline_excluded(self):
        for baseline in (row('every',complete=False),row('every',contaminated=True)):
            _,pairs=compare([baseline,row('period2',cost=50)])
            self.assertEqual(pairs,[])
        _,pairs=compare([row('every'),row('period2',contaminated=True,cost=50)])
        self.assertEqual(pairs,[])

    def test_failures_remain_in_complete_denominator(self):
        aggregate,_=compare([row('every'),row('period4',complete=False,cost=10)])
        summary=next(r for r in aggregate if r['policy']=='period4')
        self.assertEqual(summary['planned_events'],4)
        self.assertEqual(summary['published'],1)
        self.assertEqual(summary['complete_route_rounds'],0)
        self.assertEqual(summary['status_counts']['blocked_by_previous_failure'],2)
        self.assertIsNone(summary['median_full_paired_speedup'])


if __name__=='__main__':unittest.main()
