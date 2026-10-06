"""独立编译数组原版、保守方向、准确投影及二者组合，恢复长期同源资产。"""
from pathlib import Path
import ast
import datetime
import hashlib
import json
import shutil
import subprocess
import zipfile

BASE=Path(__file__).resolve().parent
WORKSPACE=BASE.parents[1]
OLD=Path('D:/GraduationProject实验输出/20261007_证书邻接复用完整反馈')
ROOT=Path('D:/GraduationProject实验输出/20261007_方向区间与投影源认证对照_v3')
PROFILE=Path('D:/GraduationProject实验输出/20261007_常驻局部质量完整长轨迹_14137_v9/21-源认证同源组件对照_20261007_004722')
CMAKE='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not ROOT.exists();ROOT.mkdir()
archive=PROFILE/'03-源认证组件完整证据.zip'
assert sha(archive)=='525febd43bdb41c31d1f4f9ee9deef332c4a4292569206aca0017796ff880983'
record=ROOT/'01-四方法独立编译与资产恢复.json'
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='running',
    source_archive_sha256=sha(archive),restored={},builds=[])


def save():
    record.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


def once(text,before,after):
    assert text.count(before)==1,before
    return text.replace(before,after)


save()
try:
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        for name in package.namelist():
            if not name.endswith('.npz'):continue
            parts=Path(name).parts
            directory=next(p for p in parts if p.startswith(('slab_','sphere_')))
            target=ROOT/'assets'/directory/parts[-1];target.parent.mkdir(parents=True,exist_ok=True)
            assert not target.exists();data=package.read(name);target.write_bytes(data)
            report['restored'][target.relative_to(ROOT).as_posix()]=dict(size=len(data),sha256=hashlib.sha256(data).hexdigest())
    assert len(report['restored'])==22
    shutil.copyfile(PROFILE/'02-精确平面排除同源组件对照.json',ROOT/'original_profile.json')
    # 复用60号已实际执行的准确投影代码，只改变它在数组图认证中的调用位置。
    profile_source=WORKSPACE/'初步实验/连续磨削长期稳定性/profile_resident_plane_certificate.py'
    tree=ast.parse(profile_source.read_text(encoding='utf-8'))
    choices=[node.value.value for node in ast.walk(tree) if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant)
             and isinstance(node.value.value,str) and any(isinstance(t,ast.Name) and t.id=='filter_code' for t in node.targets)]
    projected=next(text for text in choices if 'using ProjectedTriangle=' in text)
    original=(BASE/'incremental_mesh_memory_array.cpp').read_text(encoding='utf-8')
    anchor='        auto callback=[&](const Box* a,const Box* b) {'
    before='            ++checked;\n            // 图接口仅替换数据读取；相交判定仍调用原CGAL共享边、共享点和普通面逻辑。'
    cmake='cmake_minimum_required(VERSION 3.20)\nproject(directional_certificate LANGUAGES CXX)\n'
    for name in ['reference','directional','projected','combined']:
        folder=ROOT/name;folder.mkdir()
        for p in (OLD/'workers').iterdir():
            if p.is_file():shutil.copyfile(p,folder/p.name)
        shutil.copyfile(BASE/'directional_bounds.h',folder/'directional_bounds.h')
        modified=once(original,'#include <limits>',
            '#include <limits>\n#include "directional_bounds.h"\n#include <cfenv>\n'
            '// 当前线程保留本次实际筛选计数，不进入证书的正确性身份。\n'
            'static thread_local std::int64_t direction_exclusions=0,projection_exclusions=0;')
        modified=once(modified,'        *next_state=nullptr;for(int i=0;i<12;++i) result[i]=0;',
            '        direction_exclusions=0;projection_exclusions=0;\n        *next_state=nullptr;for(int i=0;i<12;++i) result[i]=0;')
        preparation=''
        filtering=''
        if name in ['directional','combined']:
            preparation+='        DirectionalBounds direction_bounds(v,nv,f,nf);\n'
            filtering+='\n            // 严格方向区间分离才跳过，其余配对继续原准确谓词。\n            if(direction_bounds.separated(i,j)) {++direction_exclusions;return;}'
        if name in ['projected','combined']:
            preparation+=projected
            filtering+='\n            // 准确投影边分离复用60号方法；零值、共线与接触继续原检查。\n            if(strictly_separated(a->info(),b->info())) {++projection_exclusions;return;}'
        modified=once(modified,anchor,preparation+anchor)
        modified=once(modified,before,before+filtering)
        (folder/'incremental_mesh_memory_array.cpp').write_text(modified,encoding='utf-8')
        source=(BASE/'incremental_mesh_memory_shared_topology.cpp').read_text(encoding='utf-8')
        source+='''\n// 组件控制直接核对保守区间，不改变原证书结果字段或固定翻边拒绝码。
EXACT_MEMORY_API void get_filter_counts(std::int64_t* out) {out[0]=direction_exclusions;out[1]=projection_exclusions;}
EXACT_MEMORY_API void get_point_direction_intervals(const double* v,std::uint64_t nv,double* out,int rounding) {
    const int previous=std::fegetround();
    if(rounding>=0) std::fesetround(rounding);
    for(std::uint64_t i=0;i<nv;++i) {
        auto bounds=DirectionalBounds::point(v+3*i);std::copy(bounds.begin(),bounds.end(),out+12*i);
    }
    std::fesetround(previous);
}
'''
        (folder/'incremental_mesh_memory.cpp').write_text(source,encoding='utf-8')
        cmake+=f'add_library({name} SHARED "{(folder/"incremental_mesh_memory.cpp").as_posix()}")\n'
        cmake+=f'target_compile_features({name} PRIVATE cxx_std_17)\ntarget_compile_definitions({name} PRIVATE CGAL_DISABLE_GMP)\n'
        cmake+=f'target_compile_options({name} PRIVATE /utf-8 /fp:strict)\ntarget_include_directories({name} PRIVATE "{(WORKSPACE/"tmp/实时预算精确整数依赖").as_posix()}")\n'
    source=ROOT/'memory_source';source.mkdir();(source/'CMakeLists.txt').write_text(cmake,encoding='utf-8')
    for stage,argv in [('configure',[CMAKE,'-S',str(source),'-B',str(ROOT/'memory_build'),'-G','Visual Studio 17 2022','-A','x64']),
                       ('build',[CMAKE,'--build',str(ROOT/'memory_build'),'--config','Release','--parallel','4'])]:
        with (ROOT/(stage+'.log')).open('x',encoding='utf-8') as log:
            code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
        report['builds'].append(dict(stage=stage,argv=argv,returncode=code,log_sha256=sha(ROOT/(stage+'.log'))));save()
        assert code==0
    for name in ['reference','directional','projected','combined']:
        folder=ROOT/name;shutil.copyfile(ROOT/f'memory_build/Release/{name}.dll',folder/'incremental_mesh_memory.dll')
        (folder/'build_identity.json').write_text(json.dumps(dict(status='completed',libraries=[dict(path=str(p),sha256=sha(p)) for p in folder.glob('*.dll')]),ensure_ascii=False,indent=2),encoding='utf-8')
    report.update(status='completed',projection_generator_sha256=sha(profile_source),
        frozen_files={str(p.relative_to(ROOT)):sha(p) for name in ['reference','directional','projected','combined'] for p in (ROOT/name).iterdir() if p.is_file()})
    save()
except Exception as error:
    report.update(status='failed',error=repr(error));save();raise
print(json.dumps(dict(status='completed',variants=4,restored=len(report['restored']))),flush=True)
