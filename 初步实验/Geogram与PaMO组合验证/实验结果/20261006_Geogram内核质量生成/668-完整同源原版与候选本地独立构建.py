"""2300份冻结源码复原后建立Windows独立原版和当前候选，不改参考库。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil
import subprocess
import time
import zipfile

here=Path(__file__).resolve().parent
project=next(p for p in here.parents if (p/'研究内容1-创新点.md').is_file())
root=project/'实验结果/Geogram原生本地同源';root.mkdir()
log_folder=here/'本地同源独立编译原始日志';log_folder.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
old=json.loads((here/'625-已保留接缝顶点免重复判定原生构建记录.json').read_text('utf8'))
freeze=json.loads((here/'651-免重复判定当前原生候选完整证据封存.json').read_text('utf8'))
source_archive=here/'667-完整2300份同源原版源码归档.zip'
recover=json.loads((here/'666-完整主树与依赖2300同源源码恢复记录.json').read_text('utf8'))
assert recover['status']=='matched_all_2300_frozen_original_bytes' and sha(source_archive)==recover['archive_sha256']
record={'生成时间':now(),'修改时间及修改内容':'首次2300同源源码本地两方法独立原生构建','文档概述':'算法源码逐字节对应远端冻结版本；Windows编译平台不同，速度不与Linux混用；未验证前不算原生效果完成',
    '索引目录':['methods','stages'],'status':'running','archive_sha256':sha(source_archive),'freeze_sha256':sha(here/'651-免重复判定当前原生候选完整证据封存.json'),
    'methods':{},'stages':[],'cmake_version':subprocess.check_output(['cmake','--version'],text=True).splitlines()[0]}
path=here/'669-完整同源原版与当前候选本地实际构建记录.json'
assert not path.exists()
def save():
    """真实阶段返回后保存，编译成功由退出码和产物共同确认。"""
    p=path.with_suffix('.tmp');p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');p.replace(path)
def run(name,args,log_index):
    """同一次原始构建日志原样保留；失败不继续依赖阶段。"""
    log=log_folder/f'{log_index:02d}-{name}.log';start=time.perf_counter()
    with log.open('xb') as output:result=subprocess.run(args,stdout=output,stderr=subprocess.STDOUT)
    record['stages'].append({'name':name,'argv':args,'returncode':result.returncode,'elapsed_seconds':time.perf_counter()-start,'log_sha256':sha(log)})
    save();print(name,result.returncode,flush=True)
    if result.returncode:raise RuntimeError(name+'实际构建失败')
save()
try:
    for index,method in enumerate(['baseline','candidate']):
        folder=root/method;source=folder/'source';source.mkdir(parents=True)
        with zipfile.ZipFile(source_archive) as z:
            assert z.testzip() is None
            for name in z.namelist():assert (source/name).resolve().is_relative_to(source.resolve())
            z.extractall(source)
        assert all(sha(source/name)==digest for name,digest in old['baseline_source_hashes'].items())
        if method=='candidate':
            for name,digest in freeze['files'].items():
                if name.startswith('mesh_'):
                    original=here/'免重复判定当前原生候选封存'/name;assert sha(original)==digest
                    shutil.copy2(original,source/'src/lib/geogram/mesh'/name)
        expected=old['baseline_source_hashes'] if method=='baseline' else old['candidate_source_hashes']
        assert all(sha(source/name)==digest for name,digest in expected.items())
        record['methods'][method]={'source_hashes':{name:sha(source/name) for name in expected},'source':str(source)};save()
        shutil.copy2(here/'03-原生布尔质量与阶段计时.cpp',folder/'driver.cpp')
        # 外层仅增加独立执行器目标与中文源码UTF8编译，不修改Geogram主树的构建文件。
        (folder/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.20)
project(NativeQuality LANGUAGES C CXX)
# 原始算法和依赖树保持，编译器按UTF8读取既有中文注释。
add_compile_options(/utf-8)
add_subdirectory(source geogram_build)
add_executable(native driver.cpp)
target_link_libraries(native PRIVATE geogram)
target_compile_features(native PRIVATE cxx_std_17)
target_compile_definitions(native PRIVATE GEO_DYNAMIC_LIBS)
set_target_properties(native PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
''','utf8')
        build=folder/'build'
        args=['cmake','-S',str(folder),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64',
            '-DVORPALINE_PLATFORM=Win-vs-dynamic-generic','-DGEOGRAM_WITH_GRAPHICS=OFF','-DGEOGRAM_WITH_TRIANGLE=ON',
            '-DGEOGRAM_WITH_TETGEN=OFF','-DGEOGRAM_WITH_HLBFGS=OFF','-DGEOGRAM_WITH_LEGACY_NUMERICS=OFF','-DGEOGRAM_WITH_LUA=OFF',
            '-DGEOGRAM_WITH_TBB=OFF','-DGEOGRAM_LIB_ONLY=ON']
        run(('原版' if method=='baseline' else '候选')+'配置',args,1+index*2)
        run(('原版' if method=='baseline' else '候选')+'Release编译',['cmake','--build',str(build),'--config','Release','--target','native','--parallel','4'],2+index*2)
        executable=build/'bin/Release/native.exe';library=build/'bin/Release/geogram.dll'
        assert executable.is_file() and library.is_file()
        record['methods'][method].update(binary=str(executable),binary_sha256=sha(executable),library=str(library),library_sha256=sha(library));save()
    record.update(status='completed_two_exact_source_windows_native_builds',finished_beijing=now());save()
except BaseException as error:
    record.update(status='failed_actual_same_source_windows_build',error=str(error),finished_beijing=now());save();raise
