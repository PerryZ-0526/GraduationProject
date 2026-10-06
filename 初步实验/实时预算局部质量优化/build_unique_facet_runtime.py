"""在私有副本中加入唯一三角面扫描，原排序在存在重复或多边形时保留。"""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
from time import perf_counter

# 首轮逐项分配版独立保留；连续内存版使用新根目录，不覆盖正在诊断的旧库。
FLAT = '--flat' in sys.argv[1:]
assert not (set(sys.argv[1:]) - {'--flat'})
ROOT = Path('/tmp/geogram_unique_facets_20261006_flat' if FLAT else '/tmp/geogram_unique_facets_20261006')
ORIGINAL = Path('/tmp/geogram_certified_pairs_20261006_r3')
WORKERS = Path('/tmp/filtered_source_certificate_20261006/workers')
EXPECTED_REPAIR_SHA = '1dfcd670516128ae8d7e9efec6ced07369c385ed1b4fea170f476e5965a6b7a5'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


ROOT.mkdir(exist_ok=False)
repair_original = ORIGINAL / 'geogram_source/src/lib/geogram/mesh/mesh_repair.cpp'
assert sha(repair_original) == EXPECTED_REPAIR_SHA
shutil.copytree(ORIGINAL / 'geogram_source', ROOT / 'geogram_source')
shutil.copytree(WORKERS, ROOT / 'workers', ignore=shutil.ignore_patterns('__pycache__'))
repair = ROOT / 'geogram_source/src/lib/geogram/mesh/mesh_repair.cpp'
text = repair.read_text(encoding='utf-8')
includes = '#include <cstdint>\n#include <vector>\n' if FLAT else '#include <array>\n#include <unordered_set>\n'
text = text.replace('#include <stack>', includes + '#include <stack>', 1)
start = text.index('            // Indirect-sort the facets in lexicographic')
end = text.index('\n\t    // Restore initial facets orientation', start)
original_sort = text[start:end]
scan = '''            // 顶点及角属性已按作者规则规范化；逐面完整扫描，不凭输入身份跳过。
            bool all_unique = false;
            if(CmdLine::get_arg_bool("algo:linear_unique_facets") && M.facets.are_simplices()) {
                struct TriangleHash {
                    std::size_t operator()(const std::array<index_t,3>& triangle) const {
                        std::size_t hash = 0;
                        for(index_t vertex: triangle) {
                            hash ^= std::hash<index_t>()(vertex) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
                        }
                        return hash;
                    }
                };
                std::unordered_set<std::array<index_t,3>,TriangleHash> seen;
                seen.reserve(M.facets.nb());
                all_unique = true;
                for(index_t f: M.facets) {
                    const std::array<index_t,3> triangle = {{
                        M.facets.vertex(f,0), M.facets.vertex(f,1), M.facets.vertex(f,2)
                    }};
                    if(!seen.insert(triangle).second) {
                        all_unique = false;
                        break;
                    }
                }
            }
            // 任一重复或多边形面均完整回退原排序及来源位异或；随后照常恢复方向和查退化。
            if(!all_unique) {
'''
if FLAT:
    scan = '''            // 顶点及角属性先按作者规则规范化；连续表只存原面编号，冲突按三顶点精确核对。
            bool all_unique = false;
            if(CmdLine::get_arg_bool("algo:linear_unique_facets") && M.facets.are_simplices()) {
                std::size_t capacity = 1;
                while(capacity < std::size_t(M.facets.nb()) * 2) capacity *= 2;
                std::vector<index_t> slots(capacity, NO_INDEX);
                all_unique = true;
                for(index_t f: M.facets) {
                    const index_t a = M.facets.vertex(f,0);
                    const index_t b = M.facets.vertex(f,1);
                    const index_t c = M.facets.vertex(f,2);
                    std::uint64_t hash = std::uint64_t(a) * 0x9e3779b97f4a7c15ULL
                        ^ std::uint64_t(b) * 0xbf58476d1ce4e5b9ULL
                        ^ std::uint64_t(c) * 0x94d049bb133111ebULL;
                    hash ^= hash >> 33;
                    hash *= 0xff51afd7ed558ccdULL;
                    hash ^= hash >> 33;
                    std::size_t slot = std::size_t(hash) & (capacity-1);
                    while(slots[slot] != NO_INDEX) {
                        const index_t other = slots[slot];
                        if(M.facets.vertex(other,0) == a && M.facets.vertex(other,1) == b
                            && M.facets.vertex(other,2) == c) {
                            all_unique = false;
                            break;
                        }
                        slot = (slot+1) & (capacity-1);
                    }
                    if(!all_unique) break;
                    slots[slot] = f;
                }
            }
            // 任一重复或多边形面均完整回退原排序及来源位异或，不改变退化处理和方向恢复。
            if(!all_unique) {
'''
text = text[:start] + scan + '\n'.join('    ' + line for line in original_sort.splitlines()) + '\n            }\n' + text[end:]
repair.write_text(text, encoding='utf-8')
adapter = ROOT / 'workers/geogram_memory.cpp'
text = adapter.read_text(encoding='utf-8')
anchor = '            GEO::CmdLine::declare_arg("algo:certified_operands", false, "Certified closed embedded operands");'
assert text.count(anchor) == 1
text = text.replace(anchor, anchor + '\n            // 私有开关默认关闭，只控制完整扫描确认唯一后的排序省略。\n            GEO::CmdLine::declare_arg("algo:linear_unique_facets", false, "Linear unique triangle scan");')
anchor = '        GEO::mesh_boolean_operation(*result, a, b, "A-B", flags);'
assert text.count(anchor) == 1
text = text.replace(anchor, '        // 每次调用显式重设，关闭模式不继承上一帧候选状态。\n        GEO::CmdLine::set_arg("algo:linear_unique_facets", (no_simplify & 4) ? "true" : "false");\n' + anchor)
adapter.write_text(text, encoding='utf-8')
wrapper = ROOT / 'workers/geogram_memory.py'
text = wrapper.read_text(encoding='utf-8')
anchor = 'no_simplify=False,certified_operands=False'
assert text.count(anchor) == 1
text = text.replace(anchor, anchor + ',linear_unique_facets=False')
anchor = 'int(no_simplify)|(2 if certified_operands else 0)'
assert text.count(anchor) == 1
text = text.replace(anchor, anchor + '|(4 if linear_unique_facets else 0)')
anchor = "'certified_operands':bool(certified_operands)"
assert text.count(anchor) == 1
text = text.replace(anchor, anchor + ",'linear_unique_facets':bool(linear_unique_facets)")
wrapper.write_text(text, encoding='utf-8')
report = {'time_beijing': stamp(), 'status': 'running', 'stages': [],
          'variant': 'flat_unique_scan' if FLAT else 'allocated_unique_scan',
          'protected_original_repair_sha256': sha(repair_original), 'candidate_repair_sha256': sha(repair),
          'builder_sha256': sha(__file__), 'new_adapter_sha256': sha(adapter), 'new_wrapper_sha256': sha(wrapper)}
record = ROOT / 'build_record.json'


def save():
    record.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def execute(name, argv):
    start = perf_counter()
    with (ROOT / (name + '.log')).open('x', encoding='utf-8') as log:
        code = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT).returncode
    report['stages'].append({'name': name, 'argv': argv, 'returncode': code, 'elapsed_ms': (perf_counter()-start)*1000})
    save()
    assert code == 0, name


save()
try:
    source = ROOT / 'geogram_source'
    build = ROOT / 'geogram_build'
    execute('01_configure', ['cmake', '-S', str(source), '-B', str(build), '-DVORPALINE_PLATFORM=Linux64-gcc-dynamic',
        '-DGEOGRAM_WITH_GRAPHICS=OFF', '-DGEOGRAM_WITH_TBB=OFF', '-DGEOGRAM_WITH_LUA=OFF',
        '-DGEOGRAM_LIB_ONLY=ON', '-DCMAKE_BUILD_TYPE=Release', '-DLINUX=ON'])
    execute('02_build', ['cmake', '--build', str(build), '--target', 'geogram', '--parallel', '4'])
    library = build / 'lib/libgeogram.so'
    execute('03_adapter', ['g++', '-std=c++17', '-O3', '-fPIC', '-shared', '-DGEO_DYNAMIC_LIBS',
        '-I' + str(source / 'src/lib'), str(adapter), '-L' + str(library.parent), '-lgeogram',
        '-Wl,-rpath,' + str(library.parent), '-o', str(ROOT / 'workers/libgeogram_memory.so')])
    inherited = json.loads((WORKERS / 'build_identity.json').read_text(encoding='utf-8'))
    libraries = [{'path': str(library), 'sha256': sha(library)},
                 {'path': str(ROOT / 'workers/libgeogram_memory.so'), 'sha256': sha(ROOT / 'workers/libgeogram_memory.so')}]
    for row in inherited['libraries']:
        if Path(row['path']).name not in ('libgeogram.so', 'libgeogram_memory.so'):
            assert sha(row['path']) == row['sha256']
            libraries.append(row)
    report['libraries'] = libraries
    assert sha(repair_original) == EXPECTED_REPAIR_SHA
    report['status'] = 'completed'
    report['finished_time_beijing'] = stamp()
    save()
    (ROOT / 'workers/build_identity.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'root': str(ROOT)}), flush=True)
except Exception as error:
    report['status'] = 'failed'
    report['error'] = repr(error)
    save()
    raise
