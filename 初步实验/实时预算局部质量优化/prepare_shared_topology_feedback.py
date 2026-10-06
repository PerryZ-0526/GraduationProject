"""从17号已封存本机工作器创建独立邻接复用版本，原证据不覆盖。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

BASE=Path(__file__).resolve().parent
OLD=Path('D:/GraduationProject实验输出/20261007_数组源证书本机完整反馈')
ROOT=Path('D:/GraduationProject实验输出/20261007_证书邻接复用完整反馈')
CMAKE='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
assert json.loads((OLD/'09-Windows扫描库身份修订完整链路执行记录.json').read_text(encoding='utf-8'))['status']=='completed'
assert not ROOT.exists();ROOT.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
record=ROOT/'01-私有邻接复用准备与编译.json'
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='running',
    previous_summary_sha256=sha(OLD/'10-本机完整四预算与Arc像素终态汇总.json'),stages=[],copied={})


def save():
    record.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


def replace_once(text,before,after):
    assert text.count(before)==1,before
    return text.replace(before,after)


save()
try:
    for name in ['workers','reference_workers']:
        current=ROOT/name;current.mkdir()
        for p in (OLD/'workers').iterdir():
            if not p.is_file():continue
            shutil.copyfile(p,current/p.name);assert sha(p)==sha(current/p.name)
            report['copied'][f'{name}/{p.name}']=sha(p)
        for source,target in [('incremental_mesh_memory_array.cpp','incremental_mesh_memory_array.cpp'),
                              ('incremental_mesh_memory_shared_topology.cpp','incremental_mesh_memory.cpp'),
                              ('certificate_activity_edges.py','certificate_activity_edges.py')]:
            shutil.copyfile(BASE/source,current/target)
        # 两方法共享相同编译库，参照仍走原排序准备；只让候选消费原证书邻接。
        if name=='workers':
            path=current/'maintain_input.py';text=path.read_text(encoding='utf-8')
            text=replace_once(text,"max_flips=16,edge_backend='cpu'):","max_flips=16,edge_backend='cpu',certificate=None):")
            text=replace_once(text,'    state=method(vertices,faces,bits,active,backend,factory)',
                "    # 复用同源证书的全局半边，仍采用原质量、活动域及碰撞守卫。\n"
                "    if certificate is not None:\n"
                "        if edge_backend!='cpu' or not targeted:raise ValueError('证书邻接当前仅支持CPU小角种子')\n"
                "        from certificate_activity_edges import CertificateBudgetFlipState\n"
                "        state=CertificateBudgetFlipState(vertices,faces,bits,active,backend,factory,certificate)\n"
                "    else:state=method(vertices,faces,bits,active,backend,factory)")
            path.write_text(text,encoding='utf-8')
            path=current/'verified_budget_feedback.py';text=path.read_text(encoding='utf-8')
            text=replace_once(text,'from incremental_mesh_memory import VerifiedMesh','from certificate_activity_edges import SharedVerifiedMesh as VerifiedMesh')
            text=replace_once(text,"edge_backend=args.edge_backend)","edge_backend=args.edge_backend,certificate=certificate)")
            path.write_text(text,encoding='utf-8')
        path=current/'verified_budget_feedback.py';text=path.read_text(encoding='utf-8')
        text=replace_once(text,"'verified_budget_feedback.py','incremental_mesh_memory.py'",
            "'certificate_activity_edges.py','incremental_mesh_memory_array.cpp','incremental_mesh_memory_filtered.cpp','verified_budget_feedback.py','incremental_mesh_memory.py'")
        text=replace_once(text,"report['edge_backend']=args.edge_backend;",f"report['certificate_topology_reuse']={name=='workers'};report['edge_backend']=args.edge_backend;")
        path.write_text(text,encoding='utf-8')
    source=ROOT/'memory_source';source.mkdir()
    dependencies=(BASE.parents[1]/'tmp/实时预算精确整数依赖').as_posix()
    (source/'CMakeLists.txt').write_text(
        'cmake_minimum_required(VERSION 3.20)\nproject(shared_quality_topology LANGUAGES CXX)\n'
        f'add_library(incremental_mesh_memory SHARED "{(ROOT/"workers/incremental_mesh_memory.cpp").as_posix()}")\n'
        'target_compile_features(incremental_mesh_memory PRIVATE cxx_std_17)\n'
        'target_compile_definitions(incremental_mesh_memory PRIVATE CGAL_DISABLE_GMP)\n'
        'target_compile_options(incremental_mesh_memory PRIVATE /utf-8 /fp:strict)\n'
        f'target_include_directories(incremental_mesh_memory PRIVATE "{dependencies}")\n',encoding='utf-8')
    for name,argv in [('configure',[CMAKE,'-S',str(source),'-B',str(ROOT/'memory_build'),'-G','Visual Studio 17 2022','-A','x64']),
                      ('build',[CMAKE,'--build',str(ROOT/'memory_build'),'--config','Release','--parallel','4'])]:
        with (ROOT/(name+'.log')).open('x',encoding='utf-8') as output:
            code=subprocess.run(argv,stdout=output,stderr=subprocess.STDOUT).returncode
        report['stages'].append(dict(name=name,returncode=code,argv=argv,log_sha256=sha(ROOT/(name+'.log'))));save()
        assert code==0,(name,code)
    library=ROOT/'memory_build/Release/incremental_mesh_memory.dll'
    for name in ['workers','reference_workers']:
        shutil.copyfile(library,ROOT/name/library.name)
        current=ROOT/name;identity=current/'build_identity.json'
        identity.write_text(json.dumps(dict(status='completed',platform='Windows',
            libraries=[dict(path=str(p),sha256=sha(p)) for p in current.glob('*.dll')]),ensure_ascii=False,indent=2),encoding='utf-8')
    report.update(status='completed',frozen_files={str(p.relative_to(ROOT)):sha(p) for name in ['workers','reference_workers'] for p in (ROOT/name).iterdir() if p.is_file()})
    save()
except Exception as error:
    report.update(status='failed',error=repr(error));save();raise
print(json.dumps(dict(status='completed',library_sha256=sha(library))),flush=True)
