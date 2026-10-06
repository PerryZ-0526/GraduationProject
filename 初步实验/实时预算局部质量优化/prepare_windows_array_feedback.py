"""从已核对归档恢复快速Geogram，在D盘独立编译同内核的原证书与数组证书工作器。"""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess
import zipfile

BASE=Path(__file__).resolve().parent
WORKSPACE=BASE.parents[1]
ROOT=Path('D:/GraduationProject实验输出/20261007_数组源证书本机完整反馈')
ARCHIVE=Path('D:/GraduationProject实验输出/20261006_实时预算局部质量算法/Linux完整连续与资源诊断证据/09-唯一面扫描四预算与GPU像素完整证据.zip')
CMAKE='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
assert not ROOT.exists()
with ARCHIVE.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()=='298aef40c21ec63345008fcb4524604430c6e3e456428346ce9a4648a6554ba4'
ROOT.mkdir()
record=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    status='running',platform='Windows MSVC',stages=[],restored={},archive_sha256='298aef40c21ec63345008fcb4524604430c6e3e456428346ce9a4648a6554ba4',
    scope='本机独立整链，不绕过GPU源码上传审批，不修改既有DLL或远端环境')
target=ROOT/'01-本机同内核独立准备与构建.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save():
    temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(target)


def execute(name,argv):
    with (ROOT/(name+'.log')).open('x',encoding='utf-8') as stream:
        code=subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT).returncode
    record['stages'].append(dict(name=name,argv=argv,returncode=code,log_sha256=sha(ROOT/(name+'.log'))));save()
    assert code==0,(name,code)


save()
try:
    with zipfile.ZipFile(ARCHIVE) as archive:
        manifest=json.loads(archive.read('01-完整成员摘要清单.json'))['members']
        prefixes={'tmp/geogram_unique_facets_20261006_flat/geogram_source/':'geogram_source',
                  'tmp/geogram_unique_facets_20261006_flat/workers/':'restored_workers',
                  'tmp/geogram_certified_pairs_20261006_r3/inputs/':'inputs'}
        for member in archive.namelist():
            for prefix,destination in prefixes.items():
                if not member.startswith(prefix):continue
                relative=member[len(prefix):]
                if not relative or (destination=='restored_workers' and Path(relative).suffix not in ['.py','.cpp','.json']):continue
                assert '..' not in Path(relative).parts and not Path(relative).is_absolute()
                path=ROOT/destination/relative;path.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(member) as source,path.open('xb') as out:shutil.copyfileobj(source,out)
                assert path.stat().st_size==manifest[member]['size'] and sha(path)==manifest[member]['sha256']
                record['restored'][member]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        save()
    execute('02_geogram_configure',[CMAKE,'-S',str(ROOT/'geogram_source'),'-B',str(ROOT/'geogram_build'),
        '-G','Visual Studio 17 2022','-A','x64','-DVORPALINE_PLATFORM=Win-vs-generic','-DVORPALINE_BUILD_DYNAMIC=ON',
        '-DGEOGRAM_WITH_GRAPHICS=OFF','-DGEOGRAM_WITH_LUA=OFF','-DGEOGRAM_WITH_TBB=OFF','-DGEOGRAM_LIB_ONLY=ON'])
    execute('03_geogram_build',[CMAKE,'--build',str(ROOT/'geogram_build'),'--config','Release','--target','geogram','--parallel','4'])
    workers=ROOT/'workers';shutil.copytree(ROOT/'restored_workers',workers)
    shutil.copyfile(workers/'incremental_mesh_memory.cpp',workers/'incremental_mesh_memory_filtered.cpp')
    shutil.copyfile(BASE/'incremental_mesh_memory_array.cpp',workers/'incremental_mesh_memory.cpp')
    # 只修订私有加载路径，算法与已冻结来源标签逻辑保持；完整DLL摘要在编译后绑定。
    for name,dll in [('exact_mesh_memory.py','exact_mesh_memory.dll'),('incremental_mesh_memory.py','incremental_mesh_memory.dll'),('native_guard.py','local_separation.dll')]:
        path=workers/name;text=path.read_text(encoding='utf-8')
        begin=text.index('        path=(');end=text.index('\n',text.index('else Path(__file__)',begin))+1
        text=text[:begin]+f"        # 本机独立工作器从旁边加载本次编译的库。\n        path=Path(__file__).with_name('{dll}')\n"+text[end:]
        path.write_text(text,encoding='utf-8')
    path=workers/'geogram_memory.py';text=path.read_text(encoding='utf-8')
    begin=text.index('        workspace=');end=text.index('        self.lib=C.CDLL',begin)
    text=text[:begin]+"        # 本机私有DLL与依赖同目录，不借用历史编译内核。\n        self.dll_directory=os.add_dll_directory(str(Path(__file__).parent))\n        path=Path(__file__).with_name('geogram_memory.dll')\n"+text[end:]
    path.write_text(text,encoding='utf-8')
    path=workers/'short_edge_scan.py';text=path.read_text(encoding='utf-8')
    text=text.replace("'libshort_edge_scan.so'","'short_edge_scan.dll'");path.write_text(text,encoding='utf-8')
    inputs=ROOT/'inputs';original=inputs/'ct_record.json';shutil.copyfile(original,inputs/'ct_record_original.json')
    ct=json.loads(original.read_text(encoding='utf-8'))
    def remap(value):
        if isinstance(value,dict):return {k:remap(v) for k,v in value.items()}
        if isinstance(value,list):return [remap(v) for v in value]
        prefix='/tmp/geogram_certified_pairs_20261006_r3/inputs/'
        return str(inputs/value[len(prefix):]) if isinstance(value,str) and value.startswith(prefix) else value
    original.write_text(json.dumps(remap(ct),ensure_ascii=False,indent=2),encoding='utf-8')
    cmake_source=ROOT/'memory_source';cmake_source.mkdir()
    include=(WORKSPACE/'tmp/实时预算精确整数依赖').as_posix()
    cpp=workers.as_posix();build=(ROOT/'geogram_build').as_posix();source=(ROOT/'geogram_source').as_posix()
    cmake=['cmake_minimum_required(VERSION 3.20)','project(windows_array_feedback LANGUAGES CXX)']
    for name,filename in [('incremental_mesh_memory','incremental_mesh_memory.cpp'),('incremental_mesh_reference','incremental_mesh_memory_filtered.cpp'),
                          ('exact_mesh_memory','exact_mesh_memory.cpp'),('local_separation','native_separation.cpp'),('short_edge_scan','native_short_edge_scan.cpp')]:
        cmake += [f'add_library({name} SHARED "{cpp}/{filename}")',f'target_compile_features({name} PRIVATE cxx_std_17)',
            f'target_compile_definitions({name} PRIVATE CGAL_DISABLE_GMP)',f'target_compile_options({name} PRIVATE /utf-8 /fp:strict)',
            f'target_include_directories({name} PRIVATE "{include}")']
    # 既有短边扫描保持原源码，CMake生成导出表供Windows加载。
    cmake += ['set_target_properties(short_edge_scan PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)',
        f'add_library(geogram_memory SHARED "{cpp}/geogram_memory.cpp")','target_compile_features(geogram_memory PRIVATE cxx_std_17)',
        'target_compile_definitions(geogram_memory PRIVATE GEO_DYNAMIC_LIBS GEOGRAM_USE_BUILTIN_DEPS)',
        'target_compile_options(geogram_memory PRIVATE /utf-8)',f'target_include_directories(geogram_memory PRIVATE "{source}/src/lib")',
        f'target_link_libraries(geogram_memory PRIVATE "{build}/lib/Release/geogram.lib")']
    (cmake_source/'CMakeLists.txt').write_text('\n'.join(cmake)+'\n',encoding='utf-8')
    execute('04_memory_configure',[CMAKE,'-S',str(cmake_source),'-B',str(ROOT/'memory_build'),'-G','Visual Studio 17 2022','-A','x64'])
    execute('05_memory_build',[CMAKE,'--build',str(ROOT/'memory_build'),'--config','Release','--parallel','2'])
    for p in (ROOT/'memory_build/Release').glob('*.dll'):shutil.copyfile(p,workers/p.name)
    shutil.copyfile(ROOT/'geogram_build/bin/Release/geogram.dll',workers/'geogram.dll')
    (workers/'build_identity.json').unlink()
    shutil.copytree(workers,ROOT/'reference_workers');reference=ROOT/'reference_workers'
    shutil.copyfile(reference/'incremental_mesh_reference.dll',reference/'incremental_mesh_memory.dll')
    shutil.copyfile(reference/'incremental_mesh_memory_filtered.cpp',reference/'incremental_mesh_memory.cpp')
    for current in [reference,workers]:
        identity=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='completed',
            variant=current.name,platform='Windows MSVC',libraries=[dict(path=str(p),sha256=sha(p)) for p in current.glob('*.dll')])
        (current/'build_identity.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding='utf-8')
    record.update(status='completed',frozen_files={str(p.relative_to(ROOT)):sha(p) for current in [reference,workers] for p in current.iterdir() if p.is_file()})
    save()
except Exception as error:
    record.update(status='failed',error=repr(error));save();raise
print(json.dumps(dict(status='completed',root=str(ROOT),restored=len(record['restored']))),flush=True)
