"""保留首轮编译失败，仅修正私有连续表的容器类型并追加构建记录。"""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess

ROOT = Path('/tmp/geogram_unique_facets_20261006_flat')
previous = ROOT / 'build_record.json'
old = json.loads(previous.read_text(encoding='utf-8'))
assert old['status'] == 'failed' and old['stages'][-1]['name'] == '02_build'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


source = ROOT / 'geogram_source'
repair = source / 'src/lib/geogram/mesh/mesh_repair.cpp'
assert sha(repair) == old['candidate_repair_sha256']
backup = ROOT / 'mesh_repair_failed_flat_01.cpp'
assert not backup.exists()
shutil.copyfile(repair, backup)
text = repair.read_text(encoding='utf-8')
assert text.count('vector<index_t> slots(capacity, NO_INDEX);') == 1
text = text.replace('vector<index_t> slots(capacity, NO_INDEX);', 'std::vector<index_t> slots(capacity, NO_INDEX);')
text = text.replace('#include <cstdint>', '#include <cstdint>\n#include <vector>', 1)
repair.write_text(text, encoding='utf-8')
report = {'time_beijing': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
          'status': 'running', 'previous_record_sha256': sha(previous), 'failed_source_sha256': sha(backup),
          'candidate_repair_sha256': sha(repair), 'resume_source_sha256': sha(__file__), 'stages': []}
record = ROOT / 'build_record_02.json'
assert not record.exists()


def save():
    record.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


save()
try:
    build = ROOT / 'geogram_build'
    library = build / 'lib/libgeogram.so'
    adapter = ROOT / 'workers/geogram_memory.cpp'
    commands = [('02_build_fixed', ['cmake', '--build', str(build), '--target', 'geogram', '--parallel', '4']),
                ('03_adapter_fixed', ['g++', '-std=c++17', '-O3', '-fPIC', '-shared', '-DGEO_DYNAMIC_LIBS',
                  '-I'+str(source/'src/lib'), str(adapter), '-L'+str(library.parent), '-lgeogram',
                  '-Wl,-rpath,'+str(library.parent), '-o', str(ROOT/'workers/libgeogram_memory.so')])]
    for name, argv in commands:
        with (ROOT/(name+'.log')).open('x') as stream:
            code = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT).returncode
        report['stages'].append({'name': name, 'argv': argv, 'returncode': code})
        save()
        assert code == 0, name
    report['libraries'] = [{'path': str(path), 'sha256': sha(path)} for path in
                            [library, ROOT/'workers/libgeogram_memory.so']]
    identity_path = Path('/tmp/filtered_source_certificate_20261006/workers/build_identity.json')
    for row in json.loads(identity_path.read_text())['libraries']:
        if Path(row['path']).name not in ('libgeogram.so', 'libgeogram_memory.so'):
            assert sha(row['path']) == row['sha256']
            report['libraries'].append(row)
    report['protected_original_repair_sha256'] = sha(Path('/tmp/geogram_certified_pairs_20261006_r3/geogram_source/src/lib/geogram/mesh/mesh_repair.cpp'))
    assert report['protected_original_repair_sha256'] == old['protected_original_repair_sha256']
    report['status'] = 'completed'
    save()
    (ROOT/'workers/build_identity.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FLAT_BUILD_COMPLETED', flush=True)
except Exception as error:
    report.update(status='failed', error=repr(error))
    save()
    raise
