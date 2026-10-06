"""冻结两版本机控制、原失败和同源配对，逐成员核对完整归档并生成中文摘要。"""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import zipfile
import numpy as np

BASE=Path(__file__).resolve().parent
WORKSPACE=BASE.parents[1]
ROOTS=[WORKSPACE/'tmp/数组源证书本机控制_20261006',WORKSPACE/'tmp/数组源证书本机控制_20261006_v2']
OUTPUT=BASE/'诊断证据/51-数组源证书两版本机完整核对与计时.json'
ARCHIVE=WORKSPACE/'tmp/数组源证书两版本机完整证据_20261006_v2.zip'
assert not ARCHIVE.exists()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stats=lambda v:dict(samples=len(v),mean_ms=float(np.mean(v)),median_ms=float(np.median(v)),p95_ms=float(np.percentile(v,95)),maximum_ms=float(np.max(v)))
variants=[]
for index,root in enumerate(ROOTS):
    controls=json.loads((root/'01-本机数组源证书执行记录.json').read_text(encoding='utf-8'))
    assert controls['status']=='completed' and all(s['returncode']==0 for s in controls['stages'])
    for name,digest in controls['libraries'].items():assert sha(root/name/'incremental_mesh_memory.dll')==digest
    topology=json.loads((root/'07-数组拓扑排序多环与非法输入控制.json').read_text(encoding='utf-8'))
    near=json.loads((root/'05-过滤谓词五十近接触尺度控制.json').read_text(encoding='gbk'))
    assert topology['controls']==58 and topology['error_controls']==3 and topology['all_decisions_identical']
    assert near['controls']==50 and near['all_decisions_identical']
    component_path=root/'02-缓存精确源证书九十六配对完整核对.json'
    component=json.loads(component_path.read_text(encoding='gbk' if index==0 else 'utf-8'))
    assert component['pairs']==96 and component['all_decisions_counters_and_parent_transitions_identical']
    assert len(component['bindings'])==32 and all(b['source_full']['embedded_closed'] and b['output_full']['embedded_closed'] for b in component['bindings'])
    for name,digest in component['method_sha256'].items():assert sha(root/'workers'/name)==digest
    assert sha(root/'reference_workers/incremental_mesh_memory.dll')==component['reference_library_sha256']
    # 根、源及翻边结果来自实际对象，不把默认编码不同的原文件重写成统一格式。
    variant=dict(name='延后可编辑网格' if index==0 else '数组翻边事务',component_sha256=sha(component_path),
        source={key:stats([row[key]['total_elapsed_ms'] for row in component['rows']]) for key in ['reference','cached']},
        flips={},topology_controls=58,illegal_array_controls=3,near_contact_controls=50,component_pairs=96,
        source_output_full_audit_bindings=32,libraries=controls['libraries'])
    for count in [False,True]:
        selected=[r for r in component['rows'] if bool(r['cached_flips']['verified_operations'])==count]
        variant['flips']['nonzero' if count else 'zero']={key:stats([r[key]['total_elapsed_ms'] for r in selected]) for key in ['reference_flips','cached_flips']}
    variants.append(variant)
transaction_path=ROOTS[1]/'12-连续数组翻边1024操作与父继承控制.json'
transactions=json.loads(transaction_path.read_text(encoding='utf-8'))
assert transactions['status']=='completed' and transactions['operations']==1024 and transactions['batches']==64
assert transactions['original_protocol_pairs']==48 and transactions['original_protocol_negative_controls']==6
assert all(r['full']['embedded_closed'] and r['array']['embedded_closed'] and r['reference']['embedded_closed'] for r in transactions['rows'])
assert transactions['actual_control_source_sha256']==sha(BASE/'verify_array_fixed_transactions.py')
for root in ROOTS:
    # 原filtered与完整核查源码是两版的共用未修改前提，随实际私有DLL一同保存。
    for name in ['incremental_mesh_memory_filtered.cpp','exact_mesh_memory.cpp']:
        shutil.copyfile(BASE/name,root/'workers'/name)
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    status='completed',platform='Windows MSVC',variants=variants,protocol_pairs=48,negative_protocol_controls=6,
    repeated_fixed_flip_batches=64,repeated_fixed_flips=1024,repeated_fixed_flip_sha256=sha(transaction_path),
    gpu_trials_status='awaiting_upload_approval',auto_review_rejection='本轮源码与验证脚本上传到用户GPU实例被认定缺少具体外传授权',
    scope='已见CT保存对象本机组件对照及固定点拓扑事务；无Linux CUDA整链、实际像素或连续磨削长期稳定性结论')
if OUTPUT.exists():
    # 首次仅归档清单拒绝，已成立的实验摘要保留；复核其实际方法和全部数据相符。
    previous=json.loads(OUTPUT.read_text(encoding='utf-8'))
    assert all(previous[key]==report[key] for key in report if key!='time_beijing')
else:OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
sources=['incremental_mesh_memory_array.cpp','incremental_mesh_memory_filtered.cpp','exact_mesh_memory.cpp','exact_mesh_memory.py',
         'run_array_certificate_trials.py','verify_array_topology.py','run_local_array_controls.py','run_local_array_component.py',
         'resume_local_array_component.py','verify_array_fixed_transactions.py','collect_local_array_evidence.py',
         'verify_cached_source_certificate.py','verify_fixed_flip_certificate.py','verify_filtered_mesh_controls.py']
files={p.relative_to(WORKSPACE).as_posix():p for root in ROOTS for p in root.rglob('*') if p.is_file()}
for name in sources:
    p=BASE/name;files[p.relative_to(WORKSPACE).as_posix()]=p
files[OUTPUT.relative_to(WORKSPACE).as_posix()]=OUTPUT
failure=BASE/'诊断证据/53-数组证据首轮路径清单核对拒绝.json';files[failure.relative_to(WORKSPACE).as_posix()]=failure
dll=WORKSPACE/'tmp/实时预算内存布尔编译/Release/exact_mesh_memory.dll';files[dll.relative_to(WORKSPACE).as_posix()]=dll
manifest={n:dict(size=p.stat().st_size,sha256=sha(p)) for n,p in files.items()}
with zipfile.ZipFile(ARCHIVE,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for member,p in sorted(files.items()):archive.write(p,member)
    archive.writestr('01-完整成员摘要清单.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(ARCHIVE) as archive:
    assert set(archive.namelist())==set(manifest)|{'01-完整成员摘要清单.json'} and archive.testzip() is None
    for member,row in manifest.items():
        assert archive.getinfo(member).file_size==row['size']
        with archive.open(member) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256']
receipt=BASE/'诊断证据/52-数组源证书两版本机完整归档核对.json';assert not receipt.exists()
receipt.write_text(json.dumps(dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    status='completed',archive=str(ARCHIVE),members=len(manifest)+1,size=ARCHIVE.stat().st_size,sha256=sha(ARCHIVE),
    all_members_size_sha256_crc_verified=True,summary_sha256=sha(OUTPUT)),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='completed',members=len(manifest)+1,size=ARCHIVE.stat().st_size,sha256=sha(ARCHIVE))),flush=True)
