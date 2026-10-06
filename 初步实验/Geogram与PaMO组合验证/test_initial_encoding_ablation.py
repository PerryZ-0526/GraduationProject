"""同输入消融须保持完整配对、可重复顺序和冻结文件摘要。"""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from run_initial_encoding_ablation import schedule, validate_inputs


class InitialEncodingAblationTests(unittest.TestCase):
    def test_schedule_contains_complete_pairs(self):
        tasks=schedule(['甲','乙','丙'],3,20261005)
        expected={(case,run,method) for case in ('甲','乙','丙') for run in range(3)
            for method in ('without_initial_anchors','with_initial_anchors')}
        self.assertEqual(len(tasks),18)
        self.assertEqual(set(tasks),expected)

    def test_schedule_repeatable(self):
        self.assertEqual(schedule(['甲','乙'],3,20261005),schedule(['甲','乙'],3,20261005))

    def test_changed_input_rejected(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'source.obj';path.write_bytes(b'original')
            sha=hashlib.sha256(path.read_bytes()).hexdigest()
            case={name:'source.obj' for name in ('source','labels','tool')}
            case.update({name+'_sha256':sha for name in ('source','labels','tool')})
            manifest=dict(cases=[case]);validate_inputs(Path(folder),manifest)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):validate_inputs(Path(folder),manifest)


if __name__=='__main__':
    unittest.main()
