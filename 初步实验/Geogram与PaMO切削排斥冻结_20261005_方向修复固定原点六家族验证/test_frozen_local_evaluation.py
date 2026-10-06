"""冻结评价入口的清单变更和计划分母负例。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from audit_followup_candidate import sha256
from run_frozen_local_evaluation import check_freeze


class FrozenLocalEvaluationTests(unittest.TestCase):
    def fixture(self,root):
        manifest=root/"01-完整范围冻结清单.json"
        manifest.write_text(json.dumps({"routes":[{"split":"evaluation","cutting_prefix_ids":["e0"]}]}),encoding="utf-8")
        audit=root/"02-连续资产审计.json";audit.write_text('{"passed":true}',encoding="utf-8")
        protocol={"method_code_sha256":{},"manifest_sha256":sha256(manifest),"asset_audit_sha256":sha256(audit),
                  "planned_routes":1,"planned_events":1}
        (root/"03-独立评价方法与输入冻结.json").write_text(json.dumps(protocol),encoding="utf-8")
        return protocol

    def test_matching_protocol_passes(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);self.fixture(root)
            self.assertEqual(check_freeze(root)["planned_events"],1)

    def test_changed_manifest_rejected(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);self.fixture(root)
            (root/"01-完整范围冻结清单.json").write_text("modified",encoding="utf-8")
            with self.assertRaises(ValueError):check_freeze(root)

    def test_incomplete_plan_rejected(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);protocol=self.fixture(root);protocol["planned_events"]=2
            (root/"03-独立评价方法与输入冻结.json").write_text(json.dumps(protocol),encoding="utf-8")
            with self.assertRaises(ValueError):check_freeze(root)


if __name__=="__main__":
    unittest.main()
