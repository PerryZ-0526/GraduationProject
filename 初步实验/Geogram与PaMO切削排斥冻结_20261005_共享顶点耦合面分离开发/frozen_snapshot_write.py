"""分块写入已读取的不可变快照，减少压缩磁盘的大块临时分配。"""
from pathlib import Path
import json
import time


def read_valid_record(path):
    # 运行器会重写记录；仅冻结读取和解析期间大小及修改时刻均不变的有效JSON。
    path = Path(path)
    for _ in range(10):
        before = path.stat()
        data = path.read_bytes()
        try:
            report = json.loads(data)
        except json.JSONDecodeError:
            report = None
        after = path.stat()
        if (report is not None and before.st_size == len(data) == after.st_size
                and before.st_mtime_ns == after.st_mtime_ns):
            return data, report
        time.sleep(.2)
    raise RuntimeError("运行记录正在变化，未生成快照；稍后重试")


def write_frozen_snapshot(path, data):
    # 二进制分块保持原始字节和摘要，已有快照禁止覆盖。
    view = memoryview(data)
    with Path(path).open("xb") as stream:
        for start in range(0, len(view), 1024*1024):
            stream.write(view[start:start+1024*1024])
