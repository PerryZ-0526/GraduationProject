"""后台真实切削、内存帧交付和Qt/VTK显示；自动模式保存实际显示延迟与完整输出复审。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,multiprocessing as mp,os,queue,sys
from pathlib import Path
from time import perf_counter
import numpy as np


def worker(channel,record,output,budget,fixed_flip_certificate,early_quality_return):
    try:
        from verified_budget_feedback import main
        sys.argv=[__file__,'--ct-record',record,'--output',str(Path(output)/'实际实时父反馈'),'--budgets',str(budget)]
        # 可视化实际选择同一原生局部证书，不将离线计时冒充显示路径。
        if fixed_flip_certificate:sys.argv.append('--fixed-flip-certificate')
        if early_quality_return:sys.argv.append('--early-quality-return')
        def publish(v,f,bits,tv,tf,event):channel.put(('frame',(v,f,bits,tv,tf,event)))
        main(publisher=publish);channel.put(('done',None))
    except Exception as error:channel.put(('error',repr(error)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ct-record',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--budget',type=int,choices=[20,50,100,200],default=200)
    p.add_argument('--fixed-flip-certificate',action='store_true')
    p.add_argument('--early-quality-return',action='store_true')
    p.add_argument('--offscreen',action='store_true');p.add_argument('--auto-close',action='store_true');args=p.parse_args()
    if args.offscreen:os.environ['QT_QPA_PLATFORM']='offscreen'
    from PyQt6 import QtCore,QtGui,QtWidgets
    import pyvista as pv
    from pyvistaqt import QtInteractor
    import trimesh
    from exact_mesh_memory import ExactMeshMemory
    args.output.mkdir(parents=True,exist_ok=False)
    input_record=json.loads(args.ct_record.read_text(encoding='utf-8'));initial_path=Path(input_record['routes'][0]['events'][0]['parent_path'])
    initial=trimesh.load(initial_path,process=False)
    qt=QtWidgets.QApplication([])
    # 隐藏Qt平台不自动装载Windows中文字体，显式装载本机微软雅黑用于状态文本。
    font_id=QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    if font_id>=0:qt.setFont(QtGui.QFont(QtGui.QFontDatabase.applicationFontFamilies(font_id)[0],11))
    window=QtWidgets.QMainWindow();window.setWindowTitle('实时预算质量维护研究演示')
    window.resize(1100,760);central=QtWidgets.QWidget();window.setCentralWidget(central);layout=QtWidgets.QVBoxLayout(central)
    status=QtWidgets.QLabel('准备真实CT连续切削，预算 '+str(args.budget)+' ms');layout.addWidget(status)
    if args.offscreen:
        # 隐藏验证使用真实离屏VTK缓冲区，再将实际像素交付给Qt；不能把空控件当作已渲染。
        plotter=pv.Plotter(off_screen=True,window_size=(1000,700));image_label=QtWidgets.QLabel();layout.addWidget(image_label)
    else:
        plotter=QtInteractor(central);layout.addWidget(plotter.interactor)
    plotter.set_background('#18212b')
    def poly(v,f):return pv.PolyData(v,np.column_stack((np.full(len(f),3),f)).ravel())
    actor=plotter.add_mesh(poly(np.asarray(initial.vertices),np.asarray(initial.faces)),color='#ead7bb',show_edges=True,edge_color='#56616b',reset_camera=True)
    window.show()
    if args.offscreen:plotter.show(auto_close=False,interactive=False)
    else:plotter._on_first_render_request();plotter.render()
    channel=mp.get_context('spawn').Queue(maxsize=2)
    process=mp.get_context('spawn').Process(target=worker,args=(channel,str(args.ct_record),str(args.output),args.budget,args.fixed_flip_certificate,args.early_quality_return));process.start()
    frames=[];snapshots=[];heartbeats=[];last_heartbeat=perf_counter();tool_actor=None;terminal=False
    timer=QtCore.QTimer();timer.setInterval(16)
    def finish():
        # 完整精确复审在实时显示结束后执行，核对的是实际交付数组，不是另一批离线网格。
        full=ExactMeshMemory();audits=[]
        for index,(v,f,bits,event) in enumerate(snapshots):
            check=full.audit(v,f);assert check['embedded_closed']
            np.savez_compressed(args.output/f'e{index:02d}_实际显示数组.npz',vertices=v,faces=f,bits=bits)
            audits.append(dict(step=event['step'],check=check,output_array_sha256=event['output_array_sha256']))
        result=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',budget_ms=args.budget,
            real_computation_process_exit_code=process.exitcode,frames=frames,rendered_count=len(frames),audits=audits,
            heartbeat_ms=heartbeats,offscreen=args.offscreen,os_present_latency_not_measured=True,
            pixel_delivery_mode='离屏VTK像素交付Qt' if args.offscreen else '原生QtInteractor',
            source_record_sha256=hashlib.sha256(args.ct_record.read_bytes()).hexdigest(),
            method_sha256={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ['live_budget_viewer.py','verified_budget_feedback.py','incremental_mesh_memory.cpp']})
        # 先保存真实计时和完整复审；截图驱动异常不能抹掉已执行的数组交付证据。
        (args.output/'01-实际切削数组交付渲染与全量复审.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        window.grab().save(str(args.output/'03-实际Qt窗口画面.png'))
        plotter.screenshot(str(args.output/'02-实际末帧VTK画面.png'))
        if args.auto_close:plotter.close();window.close();qt.quit()
    def poll():
        nonlocal actor,tool_actor,last_heartbeat,terminal
        now=perf_counter();heartbeats.append((now-last_heartbeat)*1000);last_heartbeat=now
        try:kind,data=channel.get_nowait()
        except queue.Empty:return
        if kind=='error':
            timer.stop();status.setText('计算失败：'+data)
            (args.output/'04-实际计算失败.json').write_text(json.dumps({'error':data},ensure_ascii=False),encoding='utf-8')
            if args.auto_close:qt.quit()
            return
        if kind=='done':
            timer.stop();terminal=True;process.join(timeout=2);finish();return
        v,f,bits,tv,tf,event=data
        assert event['step']==len(frames) and event['source_check']['embedded_closed']
        h=hashlib.sha256()
        for array in (v,f,bits):h.update(memoryview(np.ascontiguousarray(array)).cast('B'))
        assert h.hexdigest()==event['output_array_sha256']
        render_start=perf_counter();plotter.remove_actor(actor,render=False)
        mesh=poly(v,f);mesh.cell_data['当前来源']=bits
        actor=plotter.add_mesh(mesh,scalars='当前来源',clim=[1,3],cmap=['#ead7bb','#f6a65f','#ef6c52'],show_edges=True,
            edge_color='#56616b',show_scalar_bar=False,reset_camera=False,render=False)
        if tool_actor is not None:plotter.remove_actor(tool_actor,render=False)
        tool_actor=plotter.add_mesh(poly(tv,tf),color='#4ed9cb',opacity=.25,reset_camera=False,render=False)
        plotter.reset_camera_clipping_range();plotter.render()
        assert plotter.render_window.GetNeverRendered()==0
        if args.offscreen:
            pixels=plotter.screenshot(return_img=True)
            # 像素范围检查只作非空控制，不在实时主线程排序七十万像素。
            assert pixels.shape[:2]==(700,1000) and int(pixels.max())-int(pixels.min())>24
            image=QtGui.QImage(pixels.data,pixels.shape[1],pixels.shape[0],pixels.strides[0],QtGui.QImage.Format.Format_RGB888).copy()
            image_label.setPixmap(QtGui.QPixmap.fromImage(image))
        end=perf_counter()
        latency=(end-event['tool_arrival_perf_counter'])*1000
        frames.append(dict(step=event['step'],maintenance_ms=event['maintenance_total_ms'],render_ms=(end-render_start)*1000,
            cut_to_vtk_render_return_ms=latency,budget_overrun=event['budget_overrun'],output_array_sha256=event['output_array_sha256']))
        snapshots.append((v,f,bits,event));status.setText(f"已更新 {len(frames)}/16  |  维护 {event['maintenance_total_ms']:.1f} ms  |  切削到显示 {latency:.1f} ms")
        print(json.dumps(frames[-1]),flush=True)
    timer.timeout.connect(poll);timer.start();qt.exec()
    # 用户关闭窗口时只退出本演示计算子进程，不操作远端实例或其他实验。
    if process.is_alive():process.terminate();process.join(timeout=5)
    channel.close()


if __name__=='__main__':main()
