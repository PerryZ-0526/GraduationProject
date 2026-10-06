"""核对原始GPU缓存不可被CPU结果污染，并拒绝复用不同输入或篡改对象。"""

import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import run_cut_exclusion_paired as paired
from audit_followup_candidate import sha256


class CutReuseTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.inputs = [self.root / name for name in ("source.obj", "labels.json", "tool.obj")]
        for path in self.inputs:
            path.write_text(path.name, encoding="utf8")
        paired.GPU_CACHE.clear()
        self.engine = SimpleNamespace(client=None, remote="/isolated_test")

    def tearDown(self):
        paired.GPU_CACHE.clear()
        self.temporary.cleanup()

    def gpu(self, engine, source, labels, tool, method, folder):
        folder.mkdir()
        (folder / "candidate.obj").write_text("original_gpu", encoding="utf8")
        (folder / "details.json").write_text(json.dumps({"stage1": "original"}), encoding="utf8")
        (folder / "worker.log").write_text("one_gpu_call", encoding="utf8")
        return {"execution": {"returncode": 0}, "method": method,
                "output_sha256": sha256(folder / "candidate.obj")}

    def test_cpu_result_does_not_replace_raw_cache(self):
        with patch.object(paired, "ORIGINAL_GPU_RUN", side_effect=self.gpu) as gpu, patch.object(paired, "execute", return_value={"returncode": 0}):
            paired.shared_gpu(self.engine, *self.inputs, "full", self.root / "first")
            # 模拟下一步CPU修正；另一分支必须拿到原始GPU输出，而不是此修正结果。
            (self.root / "first/candidate.obj").write_text("cpu_changed", encoding="utf8")
            row = paired.shared_gpu(self.engine, *self.inputs, "full", self.root / "second")
            self.assertTrue(row["gpu_execution_not_repeated"])
            self.assertEqual((self.root / "second/candidate.obj").read_text("utf8"), "original_gpu")
            self.assertEqual(gpu.call_count, 1)

    def test_each_input_change_requires_new_gpu_output(self):
        with patch.object(paired, "ORIGINAL_GPU_RUN", side_effect=self.gpu) as gpu, patch.object(paired, "execute", return_value={"returncode": 0}):
            paired.shared_gpu(self.engine, *self.inputs, "full", self.root / "first")
            for index, path in enumerate(self.inputs):
                path.write_text("changed_" + path.name, encoding="utf8")
                row = paired.shared_gpu(self.engine, *self.inputs, "full", self.root / str(index))
                self.assertFalse(row.get("gpu_execution_not_repeated", False))
            self.assertEqual(gpu.call_count, 4)

    def test_tampered_raw_output_is_rejected(self):
        with patch.object(paired, "ORIGINAL_GPU_RUN", side_effect=self.gpu), patch.object(paired, "execute", return_value={"returncode": 0}):
            paired.shared_gpu(self.engine, *self.inputs, "full", self.root / "first")
            (self.root / "first/raw_for_equal_input_reuse.obj").write_text("tampered", encoding="utf8")
            with self.assertRaises(ValueError):
                paired.shared_gpu(self.engine, *self.inputs, "full", self.root / "second")


if __name__ == "__main__":
    unittest.main()
