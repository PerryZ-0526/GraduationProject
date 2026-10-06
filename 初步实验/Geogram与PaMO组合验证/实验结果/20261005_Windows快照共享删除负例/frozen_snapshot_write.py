"""分块写入已读取的不可变快照，减少压缩磁盘的大块临时分配。"""
from pathlib import Path
import json
import time
import os


def open_shared_record(path):
    """Windows读快照允许写入器原子替换，其他平台沿用普通只读。"""
    if os.name != 'nt':
        return Path(path).open('rb')
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    # 共享读、写、删除；读句柄继续指向旧完整对象，不阻止新记录替换路径。
    handle = create(str(Path(path).resolve()), 0x80000000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    return os.fdopen(descriptor, 'rb')


def read_shared_record_bytes(path):
    with open_shared_record(path) as stream:
        return stream.read()


def read_valid_record(path):
    # 运行器会重写记录；仅冻结读取和解析期间大小及修改时刻均不变的有效JSON。
    path = Path(path)
    for _ in range(10):
        before = path.stat()
        data = read_shared_record_bytes(path)
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
