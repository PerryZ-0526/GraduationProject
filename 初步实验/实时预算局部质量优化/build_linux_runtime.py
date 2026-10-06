"""在独立目录从冻结源码编译Linux完整内存链，保存每阶段实际日志与摘要。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,subprocess,zipfile
from pathlib import Path
from time import perf_counter


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--resume',action='store_true');p.add_argument('--attempt',type=int,default=1)
    p.add_argument('--worker-manifest',default='manifest.json');args=p.parse_args()
    root=args.root.resolve();sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    attempt=2 if args.resume else args.attempt;assert attempt>=1
    dependencies={'OpenNL':('opennl.zip','ae782db2db40cc40fcd7659629fc652e5eab1f9e'),
        'amgcl':('amgcl.zip','93827a00fc926d951c75f08fdb1d491912ff7065'),
        'libMeshb':('libmeshb.zip','88095d5ed04bfaf6bee27b777e7190bebdc72230'),
        'rply':('rply.zip','4296cc91b5c8c26d4e7d7aac0cee2b194ffc5800')}
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',stages=[],
        geogram_archive_sha256=sha(root/'geogram.zip'),worker_archive_sha256=sha(root/'workers.zip'),
        dependencies={name:dict(archive=archive,sha256=sha(root/archive),commit=commit) for name,(archive,commit) in dependencies.items()})
    # 每次恢复只追加独立记录和日志，不改写此前缺少子模块的实际失败。
    prefix=f'{attempt:02d}_' if attempt>1 else '';out=root/(f'build_record_{attempt:02d}.json' if attempt>1 else 'build_record.json');assert not out.exists()
    def save():
        temporary=out.with_suffix('.tmp');temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(out)
    def execute(name,argv):
        start=perf_counter();log=root/(prefix+name+'.log')
        with log.open('x',encoding='utf-8') as stream:result=subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT)
        report['stages'].append(dict(name=name,argv=argv,returncode=result.returncode,elapsed_ms=(perf_counter()-start)*1000,log_sha256=sha(log)))
        save()
        if result.returncode:raise RuntimeError('实际编译阶段失败：'+name)
    save()
    try:
        geo=root/'geogram_source'
        if attempt>1:
            previous=root/(f'build_record_{attempt-1:02d}.json' if attempt>2 else 'build_record.json')
            assert geo.exists() and json.loads(previous.read_text())['status'] in ('failed','completed')
        else:
            assert not geo.exists()
            with zipfile.ZipFile(root/'geogram.zip') as z:z.extractall(geo)
            with zipfile.ZipFile(root/'workers.zip') as z:z.extractall(root)
        # 补齐Geogram固定的四个非图形依赖，公共作者目录和旧实例库都不修改。
        for name,(archive,_) in dependencies.items():
            with zipfile.ZipFile(root/archive) as z:z.extractall(geo/'src/lib/geogram/third_party'/name)
        # 原始归档清单不覆盖；修正构建适配文件后使用独立追加清单逐项绑定。
        manifest_path=root/args.worker_manifest;assert manifest_path.resolve().parent==root
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'));report['worker_manifest_sha256']=sha(manifest_path)
        for row in manifest:assert sha(root/row['name'])==row['sha256']
        report['worker_and_input_members_verified']=len(manifest)
        build=root/'geogram_build'
        execute('01_configure_geogram',['cmake','-S',str(geo),'-B',str(build),'-DVORPALINE_PLATFORM=Linux64-gcc-dynamic',
            '-DGEOGRAM_WITH_GRAPHICS=OFF','-DGEOGRAM_WITH_TBB=OFF','-DGEOGRAM_WITH_LUA=OFF','-DGEOGRAM_LIB_ONLY=ON','-DCMAKE_BUILD_TYPE=Release',
            # 旧CMake没有预定义LINUX；显式启用作者原有Linux标准库TBB链接分支。
            '-DLINUX=ON'])
        execute('02_build_geogram',['cmake','--build',str(build),'--target','geogram','--parallel','4'])
        library=build/'lib/libgeogram.so';assert library.exists()
        workers=root/'workers';native=root/'native_build'
        execute('03_configure_native',['cmake','-S',str(workers/'linux_build'),'-B',str(native),'-DCMAKE_BUILD_TYPE=Release',
            '-DGEOGRAM_SOURCE='+str(geo),'-DGEOGRAM_LIBRARY='+str(library)])
        execute('04_build_native',['cmake','--build',str(native),'--parallel','4'])
        libraries=[library]+[workers/((('' if n=='local_separation' else 'lib')+n)+'.so')
            for n in ['geogram_memory','local_separation','exact_mesh_memory','incremental_mesh_memory']]
        report['libraries']=[dict(path=str(path),sha256=sha(path)) for path in libraries]
        report['status']='completed';save()
        (workers/'build_identity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'status':'completed','libraries':len(libraries)}),flush=True)
    except Exception as error:
        report['status']='failed';report['error']=repr(error);save();raise


if __name__=='__main__':main()
