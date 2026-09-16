"""只读枚举本机OpenCL GPU设备，不安装驱动，不进行GPU性能推断。"""
import ctypes as ct
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta


def probe():
    library = ct.WinDLL('OpenCL.dll')
    pointer, uint = ct.c_void_p, ct.c_uint
    library.clGetPlatformIDs.argtypes = [uint, ct.POINTER(pointer), ct.POINTER(uint)]
    library.clGetDeviceIDs.argtypes = [pointer, ct.c_ulonglong, uint, ct.POINTER(pointer), ct.POINTER(uint)]
    library.clGetDeviceInfo.argtypes = [pointer, uint, ct.c_size_t, pointer, ct.POINTER(ct.c_size_t)]
    count = uint()
    status = library.clGetPlatformIDs(0, None, ct.byref(count))
    if status:
        return dict(platform_status=status, devices=[])
    platforms = (pointer*count.value)()
    if library.clGetPlatformIDs(count, platforms, None):
        raise RuntimeError('OpenCL平台枚举失败')
    devices = []
    for platform in platforms:
        number = uint()
        status = library.clGetDeviceIDs(platform, 4, 0, None, ct.byref(number))
        if status == -1:
            continue
        if status:
            devices.append(dict(enumeration_error=status))
            continue
        handles = (pointer*number.value)()
        if library.clGetDeviceIDs(platform, 4, number, handles, None):
            raise RuntimeError('OpenCL GPU枚举失败')
        for handle in handles:
            row = {}
            for name, key in [('name', 0x102B), ('driver', 0x102D), ('version', 0x102F), ('extensions', 0x1030)]:
                size = ct.c_size_t()
                if library.clGetDeviceInfo(handle, key, 0, None, ct.byref(size)):
                    raise RuntimeError('OpenCL设备信息查询失败')
                buffer = ct.create_string_buffer(size.value)
                if library.clGetDeviceInfo(handle, key, size.value, buffer, None):
                    raise RuntimeError('OpenCL设备信息读取失败')
                row[name] = buffer.value.decode('utf-8')
            row['advertises_cl_khr_fp64'] = 'cl_khr_fp64' in row['extensions'].split()
            devices.append(row)
    return dict(platform_status=0, devices=devices)


if __name__ == '__main__':
    result = probe()
    result['timestamp'] = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    target = Path(__file__).parent/'实验结果/hardware.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
