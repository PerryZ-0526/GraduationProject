"""从当前原版源码建立两份独立构建，只有候选三份内部生成源码不同。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import shutil
import subprocess
import sys
import time
import argparse

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--resume',action='store_true')
parser.add_argument('--attempt',type=int,default=1)
args=parser.parse_args()
original=Path('/root/autodl-tmp/graduation_project/followup_20260928_2344/geogram_src')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
record={'生成时间':now(),'修改时间及修改内容':'首次同配置编译原版及内核质量生成候选',
        '文档概述':'只修改隔离副本，不安装覆盖原版','索引目录':['stages'], 'status':'running','stages':[]}
path=root/(f'build_record_{args.attempt:02d}.json' if args.resume else 'build_record.json')
assert not path.exists()
if args.resume:
    # 仅恢复已确认终止的构建；前次失败记录及日志保持原字节。
    assert args.attempt>1
    prior=root/(f'build_record_{args.attempt-1:02d}.json' if args.attempt>2 else 'build_record.json')
    assert json.loads(prior.read_text('utf8'))['status']=='failed_actual_native_build'
    record['prior_record_sha256']=sha(prior)
    record['build_fix']='显式链接现有libtbb，以满足GCC并行STL的符号依赖'


def save():
    """每阶段返回后原子保存实际状态。"""
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
    temporary.replace(path)


def execute(name,command_argv):
    """实际返回码和时间独立记录，编译完成不由日志存在推断。"""
    # 恢复构建使用新日志文件，不能覆盖首次链接失败现场。
    if args.resume: name=name+f'_r{args.attempt}'
    log=root/(name+'.log')
    start=time.perf_counter()
    with log.open('x') as stream:
        result=subprocess.run(command_argv,stdout=stream,stderr=subprocess.STDOUT)
    record['stages'].append({'name':name,'argv':command_argv,'returncode':result.returncode,
                             'elapsed_seconds':time.perf_counter()-start,'log_sha256':sha(log)})
    save()
    print(name,result.returncode,flush=True)
    if result.returncode: raise RuntimeError(name+'编译阶段失败')


save()
try:
    for method in ('baseline','candidate'):
        source=root/(method+'_source')
        # 原版恢复复用逐文件一致的源码，尚未开始的候选仍创建独立源码目录。
        if source.exists():
            assert args.resume
        else:
            shutil.copytree(original,source,ignore=shutil.ignore_patterns('build','.git'))
        if method=='candidate':
            for patch in (root/'patch').iterdir():
                shutil.copy2(patch,source/'src/lib/geogram/mesh'/patch.name)
        record[method+'_source_hashes']={str(p.relative_to(source)):sha(p)
            for p in source.rglob('*') if p.is_file()}
        save()
        build=root/(method+'_build')
        execute(method+'_configure',['cmake','-S',str(source),'-B',str(build),
            '-DVORPALINE_PLATFORM=Linux64-gcc-dynamic','-DCMAKE_BUILD_TYPE=Release',
            '-DGEOGRAM_WITH_GRAPHICS=OFF','-DGEOGRAM_WITH_TRIANGLE=ON','-DGEOGRAM_WITH_TETGEN=OFF',
            '-DGEOGRAM_WITH_HLBFGS=OFF','-DGEOGRAM_WITH_LEGACY_NUMERICS=OFF',
            '-DGEOGRAM_WITH_LUA=OFF','-DGEOGRAM_WITH_TBB=OFF','-DCMAKE_CXX_STANDARD_LIBRARIES=-ltbb'])
        execute(method+'_build',['cmake','--build',str(build),'--target','geogram','-j','4'])
        lib=build/'lib'
        execute(method+'_driver',['g++','-O3','-std=c++17',str(root/'driver.cpp'),
            '-I'+str(source/'src/lib'),'-L'+str(lib),'-Wl,-rpath,'+str(lib),'-lgeogram','-o',str(root/method)])
        record[method+'_binary_sha256']=sha(root/method)
        record[method+'_library_sha256']=sha(lib/'libgeogram.so')
        save()
    record.update(status='completed_two_isolated_native_builds',finished_beijing=now())
    save()
except BaseException as error:
    record.update(status='failed_actual_native_build',error_type=type(error).__name__,error=str(error),finished_beijing=now())
    save()
    raise
