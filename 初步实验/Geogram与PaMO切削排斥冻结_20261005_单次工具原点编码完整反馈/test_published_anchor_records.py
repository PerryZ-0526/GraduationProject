"""新增锚点运行记录必须有完整重算、合法新点身份及一致数量。"""
import copy
import unittest
from audit_published_anchor_records import check_anchor_record, check_absent_anchor_record


class AnchorRecordTests(unittest.TestCase):
    def test_missing_record_only_for_documented_identity(self):
        attempt = dict(projection="no_free_vertices_identity", anchor_record_available=False)
        self.assertTrue(check_absent_anchor_record(attempt))
        for changes in (dict(projection="projection"), dict(anchor_record_available=True),
                        dict(anchor_updates={"updates": []})):
            self.assertFalse(check_absent_anchor_record(dict(attempt, **changes)))

    def setUp(self):
        self.record = dict(initial_anchor_count=1, current_anchor_count=2, updates=[dict(
            diff_call=1, added_vertices=[1], encoded_initial_exact=True, full_energy_recomputed=True,
            recomputed_energy_finite=True, recomputed_energy=4.25)])
        self.ids = [0, -1, -1]

    def test_valid_update_and_unchanged_mask(self):
        self.assertTrue(check_anchor_record(self.record, self.ids))
        self.assertTrue(check_anchor_record(dict(initial_anchor_count=1, current_anchor_count=1, updates=[]), self.ids))

    def test_old_cache_and_nonfinite_recompute_rejected(self):
        for changes in (dict(full_energy_recomputed=False), dict(recomputed_energy=None),
                        dict(recomputed_energy=float("inf")), dict(recomputed_energy_finite=False)):
            record = copy.deepcopy(self.record)
            record["updates"][0].update(changes)
            self.assertFalse(check_anchor_record(record, self.ids))

    def test_wrong_time_or_original_vertex_rejected(self):
        for changes in (dict(diff_call=2), dict(encoded_initial_exact=False),
                        dict(added_vertices=[0]), dict(added_vertices=[3])):
            record = copy.deepcopy(self.record)
            record["updates"][0].update(changes)
            self.assertFalse(check_anchor_record(record, self.ids))

    def test_duplicate_or_inconsistent_counts_rejected(self):
        record = copy.deepcopy(self.record)
        record["updates"].append(copy.deepcopy(record["updates"][0]))
        self.assertFalse(check_anchor_record(record, self.ids))
        record = copy.deepcopy(self.record)
        record["current_anchor_count"] = 3
        self.assertFalse(check_anchor_record(record, self.ids))


if __name__ == "__main__":
    unittest.main()
