"""分块原子保存实验记录，写入失败时保留上一次有效记录。"""
import os
import time
from pathlib import Path


def write_chunks(stream, data):
    # 控制单次临时磁盘分配，不改变序列化结果的字节。
    view = memoryview(data)
    for start in range(0, len(view), 1024*1024):
        stream.write(view[start:start+1024*1024])


def atomic_write_text(path, text):
    path = Path(path)
    temporary = path.with_name(path.name+".writing")
    # 保留原Path.write_text的本平台换行格式；中断临时文件保留以便诊断。
    data = text.replace("\n", os.linesep).encode("utf-8")
    with temporary.open("xb") as stream:
        write_chunks(stream, data)
        stream.flush()
        os.fsync(stream.fileno())
    # Windows短暂读占用可能拒绝替换；仅对权限异常有限重试，持续失败保留两份证据。
    for attempt in range(20):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.1)
