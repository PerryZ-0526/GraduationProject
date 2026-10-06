"""等值面补查必须绑定完整终态和明确解析体，不能靠案例名称猜参照。"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
from audit_analytic_long_reference import validate


class AnalyticLongReferenceTests(unittest.TestCase):
    def test_running_record_is_rejected_before_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);prepared=root/'prepared';run=root/'run'
            prepared.mkdir();run.mkdir()
            (prepared/'01-完整范围冻结清单.json').write_text('{}',encoding='utf-8')
            (run/'01-反馈执行与独立审计.json').write_text(json.dumps(dict(status='running',split='long')),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'完整长路线终态'):
                validate(prepared,run)

    def test_missing_analytic_identity_cannot_be_guessed_from_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);prepared=root/'prepared';run=root/'run'
            prepared.mkdir();run.mkdir()
            routes=[dict(id=name,split='long',body='ct',cutting_prefix_ids=list(range(24))) for name in ('sphere','slab')]
            (prepared/'01-完整范围冻结清单.json').write_text(json.dumps(dict(routes=routes)),encoding='utf-8')
            from audit_followup_candidate import sha256
            digest=sha256(prepared/'01-完整范围冻结清单.json')
            (run/'01-反馈执行与独立审计.json').write_text(json.dumps(dict(status='completed_with_recorded_failures',split='long',manifest_sha256=digest)),encoding='utf-8')
            # 此夹具只检验身份门控，不把文本清单当作有效网格或已完成父链。
            with patch('audit_analytic_long_reference.require_complete_route'):
                with self.assertRaisesRegex(ValueError,'缺少解析体身份'):
                    validate(prepared,run)


if __name__=='__main__':
    unittest.main()
