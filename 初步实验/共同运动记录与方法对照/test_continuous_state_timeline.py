import unittest

from continuous_state_timeline import refresh_timeline, schedule


def record(step, wall_ms, accepted=True):
    return {
        "step": step,
        "wall_ms": wall_ms,
        "accepted": accepted,
        "state": {"step": step},
    }


class ContinuousStateTimelineTests(unittest.TestCase):
    def test_fifo_computes_every_event_without_drop(self):
        rows = schedule(
            [record(0, 0.0), record(1, 80.0), record(2, 120.0)],
            100.0,
        )
        self.assertEqual([row["event_id"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["arrival_ms"], 0.0)
        self.assertEqual(rows[1]["arrival_ms"], 100.0)
        self.assertEqual(rows[1]["start_ms"], 100.0)
        self.assertEqual(rows[1]["completion_ms"], 220.0)

    def test_overload_accumulates_queue_instead_of_dropping(self):
        records = [record(0, 0.0)] + [
            record(step, 250.0) for step in range(1, 5)
        ]
        rows = schedule(records, 100.0)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1]["event_id"], 4)
        self.assertEqual(rows[-1]["queue_wait_ms"], 450.0)
        self.assertEqual(rows[-1]["completion_age_ms"], 700.0)

    def test_refresh_publishes_matching_monotone_versions(self):
        rows = schedule(
            [record(0, 0.0), record(1, 80.0), record(2, 120.0)],
            100.0,
        )
        publications = refresh_timeline(rows, 50.0)
        versions = [row["published_version"] for row in publications]
        self.assertEqual(versions[-1], 2)
        self.assertTrue(
            all(first <= second for first, second in zip(versions, versions[1:]))
        )
        self.assertTrue(
            all(
                row["published_version"] == row["state_version"]
                for row in publications
            )
        )


if __name__ == "__main__":
    unittest.main()
