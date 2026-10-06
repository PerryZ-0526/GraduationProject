"""完整归档两版实际源码、控制、保存数组及CUDA反馈；不覆盖原失败记录。"""
from pathlib import Path
import datetime
import hashlib
import json
import zipfile

ROOTS = [Path('/tmp/geogram_unique_facets_20261006'), Path('/tmp/geogram_unique_facets_20261006_flat')]
ROOT = ROOTS[1]
driver = json.loads((ROOT/'03-唯一面扫描完整CUDA四预算反馈执行记录.json').read_text())
summary = json.loads((ROOT/'04-唯一面扫描四预算与真实GPU像素终态汇总.json').read_text())
assert driver['status'] == summary['status'] == 'completed'
assert len(driver['trials']) == 6 and len(driver['renders']) == 3 and summary['planned_events'] == 384
extras = [Path('/tmp')/name for name in [
    'build_unique_facet_runtime_20261006.py', 'build_unique_facet_runtime_20261006.log',
    'build_unique_facet_runtime_flat_20261006.py', 'build_unique_facet_runtime_flat_20261006.log',
    'resume_unique_facet_flat_build_20261006.py', 'resume_unique_facet_flat_build_20261006.log',
    'run_unique_facet_trials_20261006.py', 'run_unique_facet_trials_20261006.log',
    'collect_unique_facet_results_20261006.py']]
# 同时保存实际初态及工具文件，避免只保留路径而依赖已经清理的旧输出。
INPUTS = Path('/tmp/geogram_certified_pairs_20261006_r3/inputs')
files = sorted({path for root in ROOTS+[INPUTS] for path in root.rglob('*') if path.is_file()} | set(extras))
archive_path = Path('/tmp/unique_facet_complete_evidence_20261006.zip')
assert not archive_path.exists()
manifest = {'time_beijing': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            'members': {}, 'source_roots': list(map(str,ROOTS)),
            'prerequisites': {'08-过滤精确谓词四预算与GPU像素完整证据.zip': 'da18948118163e4802ca5f43baa5640e7d75965550f1413870dad96f53f94c58',
                             '07-缓存源认证四预算与GPU像素完整证据.zip': '012d9184ed3459e08c8f07f7d766f6d926c8ed88cfb15c5ee2bd36b57651249d',
                             '05-紧凑短边修复四预算与GPU像素完整证据.zip': 'f13d575dff2e095d6435fcdbb5a38969b0261adaf1e9c062202fa4cfb9ef4569',
                             '06-紧凑修复继承Geogram动态库名称补充.zip': 'bba4faf45400fed3a829196cdc485e26148d87b909599b574bce46bb5550f5b0'}}
with zipfile.ZipFile(archive_path, 'x', zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
    for path in files:
        # 动态库别名也保存其实际字节，恢复不依赖远端剩余的符号链接。
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream,'sha256').hexdigest()
        name = path.as_posix().lstrip('/')
        manifest['members'][name] = {'size': path.stat().st_size, 'sha256': digest}
        archive.write(path, name)
    archive.writestr('01-完整成员摘要清单.json', json.dumps(manifest,ensure_ascii=False,indent=2))
with archive_path.open('rb') as stream:
    digest = hashlib.file_digest(stream,'sha256').hexdigest()
receipt = {'time_beijing': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
           'status': 'completed', 'archive': str(archive_path), 'sha256': digest,
           'size': archive_path.stat().st_size, 'members': len(manifest['members'])+1,
           'prerequisites': manifest['prerequisites']}
out = ROOT/'05-唯一面扫描完整证据归档回执.json'
assert not out.exists()
out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt),flush=True)
