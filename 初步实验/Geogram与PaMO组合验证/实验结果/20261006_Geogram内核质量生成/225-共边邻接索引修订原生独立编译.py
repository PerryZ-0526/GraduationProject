"""基于首轮实际源码构建零位移修复版本，原版基线只读复用并校验。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import shutil
import subprocess
import time

root=Path(__file__).resolve().parent
prior=Path('/tmp/geogram_native_quality_20261006_02')
old=json.loads((prior/'build_record_03.json').read_text('utf8'))
assert old['status']=='completed_two_isolated_native_builds'
expected=json.loads((root/'source_manifest.json').read_text('utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
record={'生成时间':now(),'修改时间及修改内容':'首次第十四轮内部零位移版本实际编译',
        '文档概述':'复用已验证原版基线；首轮源码及库保持不变','索引目录':['stages'],
        'status':'running','stages':[],'prior_build_sha256':sha(prior/'build_record_03.json'),
        'baseline_binary_sha256':old['baseline_binary_sha256'],'baseline_library_sha256':old['baseline_library_sha256'],
        'baseline_source_hashes':old['baseline_source_hashes'],'source_manifest_sha256':sha(root/'source_manifest.json')}
assert sha(prior/'baseline')==record['baseline_binary_sha256']
assert sha(prior/'baseline_build/lib/libgeogram.so')==record['baseline_library_sha256']
path=root/'build_record.json';assert not path.exists()


def save():
    """记录真实执行状态，源码准备不计为编译成功。"""
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');temporary.replace(path)


def execute(name,args):
    """构建日志、阶段耗时和实际返回码绑定保存。"""
    log=root/(name+'.log');start=time.perf_counter()
    with log.open('x') as stream: result=subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT)
    record['stages'].append({'name':name,'argv':args,'returncode':result.returncode,
                             'elapsed_seconds':time.perf_counter()-start,'log_sha256':sha(log)})
    save();print(name,result.returncode,flush=True)
    if result.returncode: raise RuntimeError(name+'实际构建失败')


save()
try:
    source=root/'candidate_source';shutil.copytree(prior/'candidate_source',source)
    for name,expected_sha in old['candidate_source_hashes'].items(): assert sha(source/name)==expected_sha
    for name,expected_sha in expected['files'].items():
        assert sha(root/'patch'/name)==expected_sha
        shutil.copy2(root/'patch'/name,source/'src/lib/geogram/mesh'/name)
    record['candidate_source_hashes']={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()};save()
    build=root/'candidate_build'
    configure=next(stage['argv'] for stage in old['stages'] if stage['name']=='candidate_configure_r3')[:]
    configure[configure.index('-S')+1]=str(source);configure[configure.index('-B')+1]=str(build)
    execute('candidate_configure',configure)
    execute('candidate_build',['cmake','--build',str(build),'--target','geogram','-j','4'])
    lib=build/'lib'
    execute('candidate_driver',['g++','-O3','-std=c++17',str(root/'driver.cpp'),'-I'+str(source/'src/lib'),
                                '-L'+str(lib),'-Wl,-rpath,'+str(lib),'-lgeogram','-o',str(root/'candidate')])
    (root/'baseline').symlink_to(prior/'baseline')
    (root/'inputs').symlink_to(prior/'inputs')
    record.update(candidate_binary_sha256=sha(root/'candidate'),candidate_library_sha256=sha(lib/'libgeogram.so'),
                  status='completed_candidate_build_with_verified_original_baseline_reuse',finished_beijing=now())
    save()
except BaseException as error:
    record.update(status='failed_actual_second_native_build',error=str(error),finished_beijing=now());save();raise
