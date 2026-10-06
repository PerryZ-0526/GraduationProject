"""验证失败扩域、全量回退与父版本保留，避免无效网格进入连续反馈。"""

from pathlib import Path
import tempfile
import unittest

from locality_feedback import digest, maintain_frame


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / "source.obj"
        self.source.write_text("布尔输入", encoding="utf-8")
        mesh = self.folder / "parent.obj"
        mesh.write_text("上次发布", encoding="utf-8")
        self.parent = {"mesh": str(mesh), "sha256": digest(mesh), "version": 7}
        self.calls = []

    def build(self, source, method, rings):
        self.assertEqual(source, self.source)
        self.assertEqual(source.read_text(encoding="utf-8"), "布尔输入")
        self.calls.append((method, rings))
        output = self.folder / f"{method}_{rings}.obj"
        output.write_text("候选", encoding="utf-8")
        return output

    def evidence(self, accepted=True):
        return dict(topology_passed=accepted, sampled_geometry_passed=True, vertex_manifold=True,
                    finite_nondegenerate=True, capacity_unchanged=True, fixed_contract_passed=True)

    def test_success_stops_without_expansion_even_with_low_quality(self):
        # 小角比例不构成有效性拒绝；通过审计立即发布，不隐藏额外尝试成本。
        evidence = self.evidence()
        evidence["angle_below_10_fraction"] = 0.3
        state, record = maintain_frame(self.parent, self.source, self.build,
                                       lambda *args: evidence, True)
        self.assertEqual(state["version"], 8)
        self.assertEqual(self.calls, [("boolean", 0)])
        self.assertTrue(record["published"])

    def test_expansion_restarts_from_source(self):
        state, record = maintain_frame(self.parent, self.source, self.build,
                                       lambda path, mode, rings: self.evidence(rings == 2), True)
        self.assertEqual(state["version"], 8)
        self.assertEqual(self.calls, [("boolean", 0), ("boolean", 2)])
        self.assertEqual(record["expansion_count"], 1)

    def test_full_fallback_has_no_local_fixed_contract(self):
        def audit(path, mode, rings):
            evidence = self.evidence()
            evidence["fixed_contract_passed"] = False
            return evidence
        state, record = maintain_frame(self.parent, self.source, self.build, audit, True)
        self.assertEqual(state["version"], 8)
        self.assertEqual(record["full_fallback_count"], 1)
        self.assertEqual(len(self.calls), 3)

    def test_all_fail_keeps_parent(self):
        state, record = maintain_frame(self.parent, self.source, self.build,
                                       lambda *args: self.evidence(False), True)
        self.assertEqual(state, self.parent)
        self.assertFalse(record["published"])
        self.assertEqual(len(self.calls), 3)

    def test_invalid_source_runs_nothing(self):
        state, record = maintain_frame(self.parent, self.source, self.build, None, False)
        self.assertEqual(state, self.parent)
        self.assertEqual(self.calls, [])

    def test_missing_audit_field_cannot_publish(self):
        state, record = maintain_frame(self.parent, self.source, self.build,
                                       lambda *args: {"topology_passed": True}, True)
        self.assertEqual(state, self.parent)
        self.assertFalse(record["published"])

    def test_exception_can_fallback(self):
        def build(source, mode, rings):
            if mode == "boolean":
                raise RuntimeError("碰撞处理失败")
            return self.build(source, mode, rings)
        state, record = maintain_frame(self.parent, self.source, build,
                                       lambda *args: self.evidence(), True)
        self.assertEqual(state["version"], 8)
        self.assertEqual(len(record["attempts"]), 3)

    def test_input_mutation_aborts(self):
        def build(source, mode, rings):
            output = self.build(source, mode, rings)
            source.write_text("意外污染", encoding="utf-8")
            return output
        with self.assertRaisesRegex(ValueError, "修改了父快照或布尔输入"):
            maintain_frame(self.parent, self.source, build, lambda *args: self.evidence(), True)


if __name__ == "__main__":
    unittest.main()
