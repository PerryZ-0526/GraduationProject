"""从已认证真实父链测Geogram内部阶段，日志计时只用于定位，不作在线性能交付。"""
import argparse
import ctypes as C
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter
import numpy as np


def load_obj(path):
    # 原始索引与无引用点必须保留，避免加载器清理改变实际阶段输入。
    v, f = [], []
    for line in Path(path).read_text().splitlines():
        if line.startswith('v '):
            v.append([float(x) for x in line.split()[1:]])
        elif line.startswith('f '):
            f.append([int(x)-1 for x in line.split()[1:]])
    return np.ascontiguousarray(v, dtype=np.float64), np.ascontiguousarray(f, dtype=np.int64)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    base, root = args.baseline.resolve(), args.root.resolve()
    run_path = base/'r0_workers/01-真实父反馈四预算完整记录.json'
    run = json.loads(run_path.read_text())
    assert run['status'] == 'completed'
    route = next(r for r in run['routes'] if r['budget_ms'] == 100)
    assert route['valid_published'] == 16
    ct_path = Path('/tmp/geogram_certified_pairs_20261006_r3/inputs/ct_record.json')
    ct = json.loads(ct_path.read_text())['routes'][0]['events']
    root.mkdir(exist_ok=False)
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    source = base/'workers/geogram_memory.cpp'
    text = source.read_text()
    marker = 'GEO::mesh_boolean_operation(*result, a, b, "A-B", flags);'
    assert text.count(marker) == 1
    # 只有私有诊断调用启用作者阶段日志，保留位0/1的实际无简化及认证输入语义。
    text = text.replace(marker, '''// 诊断位仅启用原作者计时；原运算、来源和交叉候选参数保持。
        GEO::Logger::instance()->set_quiet((no_simplify & 4)==0);
        if(no_simplify & 4) flags=static_cast<GEO::MeshBooleanOperationFlags>(int(flags)|int(GEO::MESH_BOOL_OPS_VERBOSE));
        '''+marker)
    # 原作者输出使用C++流，必须在每次调用结束刷新后才能把阶段日志绑定帧标记。
    text = '#include <iostream>\n#include <cstdio>\n'+text
    text += '\n// 只刷新诊断输出，不改变布尔运算与结果。\nMEMORY_API void flush_profile_logs() { std::cout.flush(); std::cerr.flush(); std::fflush(nullptr); }\n'
    cpp = root/'geogram_stage_profile.cpp'
    cpp.write_text(text)
    geo = Path('/tmp/geogram_certified_pairs_20261006_r3')
    library = root/'libgeogram_stage_profile.so'
    argv = ['g++', '-std=c++17', '-O3', '-DNDEBUG', '-shared', '-fPIC', str(cpp),
        '-I'+str(geo/'geogram_source/src/lib'), '-L'+str(geo/'geogram_build/lib'), '-lgeogram',
        '-Wl,-rpath,'+str(geo/'geogram_build/lib'), '-o', str(library)]
    with (root/'compile.log').open('x') as log:
        result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT)
    assert result.returncode == 0
    lib = C.CDLL(str(library))
    ptr, count = C.c_void_p, C.c_uint64
    lib.difference_arrays.argtypes = [ptr,count,ptr,count,ptr,count,ptr,count,ptr,ptr,ptr,count,C.c_int]
    lib.difference_arrays.restype = ptr
    lib.copy_result.argtypes = [ptr,ptr,ptr,ptr]
    lib.release_result.argtypes = [ptr]
    lib.copy_result.restype = lib.release_result.restype = None
    lib.flush_profile_logs.argtypes = []
    lib.flush_profile_logs.restype = None
    rows = []
    for step, event in enumerate(route['events']):
        parent = Path(ct[0]['parent_path']) if step == 0 else Path(route['events'][step-1]['output_path'])
        tool = Path(ct[step]['tool_path'])
        expected = run['initial_sha256'] if step == 0 else route['events'][step-1]['output_sha256']
        assert sha(parent) == expected and sha(tool) == run['tool_sha256'][step]
        av, af = load_obj(parent)
        bv, bf = load_obj(tool)
        for repeat in range(4):
            print(json.dumps(dict(profile_step=step, repeat=repeat, warmup=repeat == 0)), flush=True)
            counts, times = np.zeros(2, dtype=np.uint64), np.zeros(3)
            error = C.create_string_buffer(1024)
            start = perf_counter()
            handle = lib.difference_arrays(av.ctypes.data,len(av),af.ctypes.data,len(af),
                bv.ctypes.data,len(bv),bf.ctypes.data,len(bf),counts.ctypes.data,times.ctypes.data,error,1024,7)
            assert handle, error.value
            v, f, labels = np.empty((int(counts[0]),3)), np.empty((int(counts[1]),3),dtype=np.int64), np.empty(int(counts[1]),dtype=np.int64)
            try:
                lib.copy_result(handle,v.ctypes.data,f.ctypes.data,labels.ctypes.data)
            finally:
                lib.release_result(handle)
                lib.flush_profile_logs()
            total = (perf_counter()-start)*1000
            saved = root/f'e{step:02d}_r{repeat}.npz'
            np.savez(saved, vertices=v, faces=f, labels=labels)
            rows.append(dict(step=step,repeat=repeat,warmup=repeat == 0,parent=str(parent),parent_sha256=expected,
                tool=str(tool),tool_sha256=sha(tool),native_ms=times.tolist(),total_ms=total,
                output=str(saved),output_sha256=sha(saved),vertices=len(v),faces=len(f)))
    report = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',
        record_sha256=sha(run_path),source_sha256=sha(source),actual_source_sha256=sha(cpp),library_sha256=sha(library),
        inherited_geogram_library_sha256=sha(geo/'geogram_build/lib/libgeogram.so'),compile_argv=argv,rows=rows,
        scope='16实际认证父和工具，每个预热一次测三次，原作者阶段日志开销存在；原始输出仅作诊断不反馈、不称发布')
    (root/'01-Geogram内部阶段实际计时与输入绑定.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
