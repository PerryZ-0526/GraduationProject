"""原子记录保持旧格式，磁盘写入或替换失败不能损坏上一记录。"""
import json
import os
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import atomic_record_write as writer


class AtomicRecordWriteTests(unittest.TestCase):
    def test_bytes_match_previous_text_format(self):
        text = json.dumps({"记录": ["中文", 1]}, ensure_ascii=False, indent=2)+"\n"
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root/"legacy.json").write_text(text, encoding="utf-8")
            writer.atomic_write_text(root/"record.json", text)
            self.assertEqual((root/"record.json").read_bytes(), (root/"legacy.json").read_bytes())
            self.assertFalse((root/"record.json.writing").exists())

    def test_failed_write_preserves_old_record(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/"record.json"
            path.write_bytes(b"original")
            def fail(stream, data):
                stream.write(data[:3])
                raise OSError(28, "模拟磁盘写满")
            with patch.object(writer, "write_chunks", side_effect=fail):
                with self.assertRaises(OSError):
                    writer.atomic_write_text(path, "replacement")
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(path.with_name("record.json.writing").read_bytes(), b"rep")

    def test_failed_replace_preserves_old_record_and_complete_temporary(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/"record.json"
            path.write_bytes(b"original")
            with patch.object(writer.os, "replace", side_effect=OSError("模拟替换失败")):
                with self.assertRaises(OSError):
                    writer.atomic_write_text(path, "replacement")
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(path.with_name("record.json.writing").read_bytes(), b"replacement")

    def test_transient_windows_permission_retry(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/"record.json"
            path.write_bytes(b"original")
            actual = writer.os.replace
            calls = []
            def transient(source, destination):
                calls.append(1)
                if len(calls) == 1:
                    raise PermissionError("模拟短暂读占用")
                actual(source, destination)
            with patch.object(writer.os, "replace", side_effect=transient), patch.object(writer.time, "sleep"):
                writer.atomic_write_text(path, "replacement")
            self.assertEqual(len(calls), 2)
            self.assertEqual(path.read_bytes(), b"replacement")

    def test_permanent_windows_permission_bounded(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/"record.json"
            path.write_bytes(b"original")
            with patch.object(writer.os, "replace", side_effect=PermissionError("模拟持续拒绝")) as replace, patch.object(writer.time, "sleep"):
                with self.assertRaises(PermissionError):
                    writer.atomic_write_text(path, "replacement")
            self.assertEqual(replace.call_count, 20)
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(path.with_name("record.json.writing").read_bytes(), b"replacement")

    @unittest.skipUnless(os.name == 'nt', '仅Windows实际文件读占用')
    def test_actual_windows_reader_release_then_replace(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'record.json';path.write_bytes(b'original')
            reader=path.open('rb')
            errors=[]
            def update():
                try:writer.atomic_write_text(path,'replacement')
                except OSError as error:errors.append(error)
            thread=threading.Thread(target=update)
            thread.start()
            # 实际读占用跨过首次替换尝试，释放后原子写入应有限重试成功。
            time.sleep(.2)
            reader.close()
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors,[])
            self.assertEqual(path.read_bytes(),b'replacement')


if __name__ == "__main__":
    unittest.main()
