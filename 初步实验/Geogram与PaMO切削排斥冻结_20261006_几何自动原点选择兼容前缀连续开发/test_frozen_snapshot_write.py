"""快照分块不能改变原字节，也不能覆盖既有记录。"""
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from frozen_snapshot_write import write_frozen_snapshot, read_valid_record


class FrozenSnapshotWriteTests(unittest.TestCase):
    def test_transient_empty_record_not_frozen(self):
        data = b'{"rows":[]}'
        empty = SimpleNamespace(st_size=0, st_mtime_ns=1)
        valid = SimpleNamespace(st_size=len(data), st_mtime_ns=2)
        with patch.object(Path, "stat", side_effect=[empty, empty, valid, valid]), \
             patch.object(Path, "read_bytes", side_effect=[b"", data]), \
             patch("frozen_snapshot_write.time.sleep"):
            actual, report = read_valid_record(Path("record.json"))
        self.assertEqual(actual, data)
        self.assertEqual(report, {"rows": []})

    def test_changing_record_cannot_be_certified(self):
        data = b'{"rows":[]}'
        stats = [SimpleNamespace(st_size=len(data), st_mtime_ns=i) for i in range(20)]
        with patch.object(Path, "stat", side_effect=stats), \
             patch.object(Path, "read_bytes", return_value=data), \
             patch("frozen_snapshot_write.time.sleep"):
            with self.assertRaises(RuntimeError):
                read_valid_record(Path("record.json"))

    def test_multibyte_snapshot_preserved(self):
        data = ('{"记录":"'+'中文'*400000+'"}').encode("utf-8")
        with TemporaryDirectory() as folder:
            path = Path(folder)/"snapshot.json"
            write_frozen_snapshot(path, data)
            self.assertEqual(path.read_bytes(), data)

    def test_existing_file_not_overwritten(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/"snapshot.json"
            path.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                write_frozen_snapshot(path, b"replacement")
            self.assertEqual(path.read_bytes(), b"original")

    def test_each_write_is_bounded(self):
        sizes = []
        class BoundedStream(io.BytesIO):
            def write(self, data):
                sizes.append(len(data))
                if len(data) > 1024*1024:
                    raise OSError("模拟大块磁盘分配失败")
                return super().write(data)
        with patch.object(Path, "open", return_value=BoundedStream()):
            write_frozen_snapshot(Path("snapshot.json"), b"x"*(3*1024*1024+7))
        self.assertEqual(sizes, [1024*1024]*3+[7])


if __name__ == "__main__":
    unittest.main()
