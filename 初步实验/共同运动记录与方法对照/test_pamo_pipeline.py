"""验证PaMO打包输入和失败审计的记录语义。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from prepare_pamo_remote import selected_inputs
from run_pamo_author import output_text


class PaMOPipelineTests(unittest.TestCase):
    def test_manifest_rejects_wrong_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "case.obj").write_text("v 0 0 0\n", encoding="utf-8")
            manifest = root / "inputs.json"
            manifest.write_text(json.dumps({"inputs": [
                {"case_id": "case", "path": "case.obj", "sha256": "0" * 64}
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "摘要不匹配"):
                selected_inputs(None, manifest)

    def test_timeout_output_accepts_bytes(self):
        self.assertEqual(output_text(b"\xffstdout"), "\ufffdstdout")
        self.assertEqual(output_text(None), "")

    def test_remote_executor_rejects_changed_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "bundle.tar.gz").write_bytes(b"changed")
            (root / "manifest.json").write_text(json.dumps({
                "archive": "bundle.tar.gz", "archive_sha256": "0" * 64
            }), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", str(HERE / "execute_pamo_remote.py"), str(root)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("本地压缩包摘要", completed.stderr)

    def test_failed_case_does_not_hide_other_case(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "case.obj"
            source.write_text("v 0 0 0\n", encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"inputs": [
                {"case_id": "failed", "source": str(source), "sha256": digest},
                {"case_id": "missing", "source": str(source), "sha256": digest},
            ]}), encoding="utf-8")
            outputs = root / "outputs"
            outputs.mkdir()
            (outputs / "remote_results.json").write_text(json.dumps({"runs": [
                {"case_id": "failed", "exit_code": 124, "output": None}
            ]}), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-B", str(HERE / "audit_pamo_outputs.py"), str(manifest), str(outputs)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 1)
            audit = json.loads((outputs / "audit.json").read_text(encoding="utf-8"))
            self.assertEqual([row["status"] for row in audit["cases"]],
                             ["execution_failed", "execution_missing"])


if __name__ == "__main__":
    unittest.main()
