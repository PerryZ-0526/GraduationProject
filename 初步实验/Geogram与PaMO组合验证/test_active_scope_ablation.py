"""消融只认可实际源码单改动，不覆盖已有证据。"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from audit_active_scope_ablation import audit


class ActiveScopeAblationTests(unittest.TestCase):
    def test_existing_result_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            result=Path(directory)/'result.json';result.write_text('旧证据',encoding='utf-8')
            with self.assertRaises(FileExistsError):
                audit(Path(directory)/'old',Path(directory)/'new',result)
            self.assertEqual(result.read_text(encoding='utf-8'),'旧证据')

    def test_extra_generator_change_is_rejected_before_reading_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=root/'old';new=root/'new'
            for folder in (old,new):
                (folder/'candidate').mkdir(parents=True)
            (old/'candidate/planar_patch.py').write_text('original',encoding='utf-8')
            (new/'candidate/planar_active_patch.py').write_text('unexpected',encoding='utf-8')
            (old/'candidate/initial_encoding_worker.py').write_text('worker',encoding='utf-8')
            (new/'candidate/active_patch_worker.py').write_text('worker',encoding='utf-8')
            with patch('audit_active_scope_ablation.build_active_source',return_value='expected'):
                with self.assertRaisesRegex(ValueError,'额外改动'):
                    audit(old,new,root/'result.json')
            self.assertFalse((root/'result.json').exists())


if __name__=='__main__':
    unittest.main()
