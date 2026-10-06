"""完整计时批次结束后准备私有渲染依赖，核实GPU后执行真实父反馈像素交付。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,sys,time


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--renderer-source',type=Path,required=True)
    p.add_argument('--output-name',default='render_trials');p.add_argument('--vtk-wheel',type=Path)
    args=p.parse_args();root=args.root.resolve()
    out=root/args.output_name;assert out.parent==root
    out.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='waiting_for_complete_timing',stages=[])
    target=out/'01-私有GPU渲染依赖与完整反馈执行记录.json'
    def save():
        temp=target.with_suffix('.tmp');temp.write_text(json.dumps(record,ensure_ascii=False,indent=2));temp.replace(target)
    env=dict(os.environ,LD_PRELOAD='/usr/lib/x86_64-linux-gnu/libstdc++.so.6')
    def execute(name,argv,cwd=out):
        log=out/(name+'.log')
        with log.open('x') as stream:r=subprocess.run(argv,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT)
        record['stages'].append(dict(name=name,argv=argv,returncode=r.returncode,log_sha256=sha(log)));save()
        assert r.returncode==0,(name,r.returncode)
    save()
    try:
        # 安装和渲染不与本线路配对计时重叠，不终止共享实例上其他进程。
        for attempt in range(240):
            batch=json.loads((root/'01-紧凑短边修复完整GPU批次执行记录.json').read_text());status=batch['status']
            if status=='completed':break
            assert status!='failed','必须先保留修复批次失败，不能绕过其控制'
            time.sleep(5)
        else:raise TimeoutError('完整配对批次等待超过二十分钟')
        record.update(status='preparing_private_dependencies',baseline=batch['baseline']);save()
        wheels=out/'wheels';wheels.mkdir();deps=out/'python_deps'
        # 已取得官方同摘要轮子时显式绑定本机传入文件，避免再次走慢镜像。
        vtk=str(args.vtk_wheel.resolve()) if args.vtk_wheel else 'vtk==9.5.2'
        if args.vtk_wheel:record['transferred_vtk_sha256']=sha(args.vtk_wheel);save()
        execute('download_wheels',[sys.executable,'-m','pip','download','--only-binary=:all:','--dest',str(wheels),
            'pyvista==0.48.4',vtk])
        execute('install_private_wheels',[sys.executable,'-m','pip','install','--no-index','--find-links',str(wheels),
            '--target',str(deps),'pyvista==0.48.4','vtk==9.5.2'])
        # 只下载并解包EGL前端；不安装到系统目录，也不替换共享驱动。
        execute('download_egl_frontend',['apt','download','libegl1'])
        debs=list(out.glob('libegl1_*.deb'));assert len(debs)==1
        execute('extract_private_egl',['dpkg-deb','-x',str(debs[0]),str(out/'egl')])
        record['dependency_archive_sha256']={str(path.relative_to(out)):sha(path) for path in [*wheels.iterdir(),*debs]};save()
        env.update(PYTHONPATH=str(deps),LD_LIBRARY_PATH=str(out/'egl/usr/lib/x86_64-linux-gnu')+':'+env.get('LD_LIBRARY_PATH',''),
                   VTK_DEFAULT_OPENGL_WINDOW='vtkEGLRenderWindow')
        # 先用实际像素和驱动字符串确认硬件，不能把软件回退渲染记作GPU显示。
        probe="import pyvista as p,json,pathlib; q=p.Plotter(off_screen=True,window_size=(320,240));q.add_mesh(p.Sphere());q.show(auto_close=False,interactive=False);im=q.screenshot(return_img=True);cap=q.render_window.ReportCapabilities();assert 'NVIDIA' in cap and im.max()-im.min()>24;pathlib.Path('02-实际GPU渲染器.json').write_text(json.dumps({'capabilities':cap,'pyvista':p.__version__}));q.screenshot('03-实际GPU控制像素.png');q.close()"
        execute('actual_gpu_pixels_control',[sys.executable,'-c',probe])
        record['status']='running';save()
        for name in ['reference_workers','workers']:
            shutil.copyfile(args.renderer_source,root/name/'render_live_gpu_feedback.py')
        for variant,budget in [('reference_workers',200),('workers',200),('workers',100)]:
            workers=root/variant;directory=out/f'{variant}_budget{budget}'
            execute(f'render_{variant}_{budget}',[sys.executable,str(workers/'render_live_gpu_feedback.py'),
                '--ct-record',str(Path(record['baseline'])/'inputs/ct_record.json'),
                '--output',str(directory),'--budget',str(budget)],workers)
        record['status']='completed';save()
    except Exception as error:
        record.update(status='failed',error=repr(error));save();raise


if __name__=='__main__':main()
