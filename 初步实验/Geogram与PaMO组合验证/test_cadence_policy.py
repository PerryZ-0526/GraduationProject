"""核对跳过、期满、质量触发、有效性修复和末帧整理的区别。"""
import unittest
from cadence_policy import maintenance_reason


def quality(faces=100,angle10=0.01,angle1=0,area10=0.001):
    return dict(total_faces=faces,angle_below_10_deg=dict(fraction=angle10,area_fraction=area10),
                angle_below_1_deg=dict(fraction=angle1))


class CadenceTests(unittest.TestCase):
    def test_periods_skip_until_due(self):
        for interval in (2,4,8):
            self.assertIsNone(maintenance_reason(f'period{interval}',interval-1,quality(),quality()))
            self.assertEqual(maintenance_reason(f'period{interval}',interval,quality(),quality()),'period_elapsed')

    def test_never_does_not_hide_mandatory_repair(self):
        self.assertIsNone(maintenance_reason('never',8,quality(),quality(),final=True,valid=False))
        self.assertEqual(maintenance_reason('period8',1,quality(),quality(),valid=False),'mandatory_validity_repair')

    def test_quality_is_a_trigger_not_a_rejection(self):
        self.assertEqual(maintenance_reason('adaptive',1,quality(angle10=0.1),quality()),'angle10_growth')
        self.assertIsNone(maintenance_reason('period8',1,quality(angle10=0.9),quality()))

    def test_adaptive_area_face_and_small_angle(self):
        self.assertEqual(maintenance_reason('adaptive',1,quality(area10=0.02),quality()),'angle10_area_growth')
        self.assertEqual(maintenance_reason('adaptive',1,quality(faces=200),quality()),'face_count_growth')
        self.assertEqual(maintenance_reason('adaptive',1,quality(angle1=0.01),quality()),'angle1_growth')

    def test_interval_and_final_flush(self):
        self.assertEqual(maintenance_reason('adaptive',8,quality(),quality()),'maximum_interval')
        self.assertEqual(maintenance_reason('period8',3,quality(),quality(),final=True),'final_flush')
        self.assertEqual(maintenance_reason('every',1,quality(),quality()),'every_cut')

    def test_invalid_policy_and_pending_are_rejected(self):
        for policy,pending in (('bad',1),('every',0)):
            with self.assertRaises(ValueError):maintenance_reason(policy,pending,quality(),quality())


if __name__=='__main__':unittest.main()
