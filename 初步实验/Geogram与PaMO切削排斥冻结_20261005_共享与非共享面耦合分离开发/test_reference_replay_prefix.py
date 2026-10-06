"""独立参照重放范围测试，确保长路线不会使用未来工具。"""
import unittest
from recover_public_reference import prefix_tools_through


class ReferenceReplayPrefixTests(unittest.TestCase):
    def test_stops_at_requested_event(self):
        route={"prefix_tools":[{"event_id":f"e{i}"} for i in range(24)]}
        self.assertEqual([t["event_id"] for t in prefix_tools_through(route,"e7")],
                         [f"e{i}" for i in range(8)])

    def test_unknown_event_rejected(self):
        with self.assertRaises(ValueError):
            prefix_tools_through({"prefix_tools":[{"event_id":"e0"}]},"e1")

    def test_duplicate_event_rejected(self):
        with self.assertRaises(ValueError):
            prefix_tools_through({"prefix_tools":[{"event_id":"e0"},{"event_id":"e0"}]},"e0")


if __name__=="__main__":
    unittest.main()
