"""同进程真实GPU父反馈交付VTK帧缓冲，计时覆盖切削、维护、渲染和像素读取。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,sys
from pathlib import Path
from time import perf_counter
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ct-record',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=int,choices=[20,50,100,200],required=True)
    args=p.parse_args();args.output.mkdir(exist_ok=False)
    import pyvista as pv
    from verified_budget_feedback import main as feedback
    from exact_mesh_memory import ExactMeshMemory
    plotter=pv.Plotter(off_screen=True,window_size=(1000,700));plotter.set_background('#18212b')
    actor=None;tool_actor=None;frames=[];snapshots=[];renderer=None
    def poly(v,f):return pv.PolyData(v,np.column_stack((np.full(len(f),3),f)).ravel())
    def publish(v,f,bits,tv,tf,event):
        nonlocal actor,tool_actor,renderer
        start=perf_counter();digest=hashlib.sha256()
        for array in (v,f,bits):digest.update(memoryview(np.ascontiguousarray(array)).cast('B'))
        assert digest.hexdigest()==event['output_array_sha256']
        if actor is not None:plotter.remove_actor(actor,render=False)
        if tool_actor is not None:plotter.remove_actor(tool_actor,render=False)
        mesh=poly(v,f);mesh.cell_data['来源']=bits
        actor=plotter.add_mesh(mesh,scalars='来源',clim=[1,3],cmap=['#ead7bb','#f6a65f','#ef6c52'],
            show_edges=True,edge_color='#56616b',show_scalar_bar=False,reset_camera=not frames,render=False)
        tool_actor=plotter.add_mesh(poly(tv,tf),color='#4ed9cb',opacity=.25,reset_camera=False,render=False)
        plotter.reset_camera_clipping_range()
        if not frames:plotter.show(auto_close=False,interactive=False)
        else:plotter.render()
        pixels=plotter.screenshot(return_img=True)
        # 真实读取的像素必须非空；它只证明帧缓冲完成，不能冒充屏幕扫描呈现。
        assert pixels.shape[:2]==(700,1000) and int(pixels.max())-int(pixels.min())>24
        end=perf_counter()
        frames.append(dict(step=event['step'],maintenance_ms=event['maintenance_total_ms'],
            cut_and_maintenance_ms=event['cut_and_maintenance_ms'],publication_render_and_read_ms=(end-start)*1000,
            tool_to_pixels_ms=(end-event['tool_arrival_perf_counter'])*1000,
            output_array_sha256=event['output_array_sha256'],pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),
            pixel_shape=list(pixels.shape),budget_overrun=event['budget_overrun']))
        # 统计、文件保存和保存对象完整复审在已结束的像素交付时钟之外单列。
        if renderer is None:renderer=plotter.render_window.ReportCapabilities()
        from PIL import Image
        Image.fromarray(pixels).save(args.output/f'e{event["step"]:02d}_实际帧缓冲.png')
        snapshots.append((v.copy(),f.copy(),bits.copy(),event))
        print(json.dumps(frames[-1]),flush=True)
    sys.argv=[__file__,'--ct-record',str(args.ct_record),'--output',str(args.output/'feedback'),
        '--budgets',str(args.budget),'--fixed-flip-certificate','--early-quality-return',
        '--edge-backend','cuda','--certified-operand-pairs']
    feedback(publisher=publish)
    full=ExactMeshMemory();audits=[]
    for v,f,bits,event in snapshots:
        check=full.audit(v,f);assert check['embedded_closed']
        path=args.output/f'e{event["step"]:02d}_实际显示数组.npz'
        np.savez_compressed(path,vertices=v,faces=f,bits=bits)
        audits.append(dict(step=event['step'],check=check,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    source=json.loads((args.output/'feedback/01-真实父反馈四预算完整记录.json').read_text())
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',
        budget_ms=args.budget,frames=frames,audits=audits,rendered_count=len(frames),planned_events=16,
        renderer_capabilities=renderer,pyvista_version=pv.__version__,os_present_latency_not_measured=True,
        user_interaction_and_queue_not_measured=True,display_scope='同步离屏实际VTK像素交付，不含屏幕扫描呈现或客户端传输',
        cold_first_render_included=True,feedback_status=source['status'],
        method_sha256={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ['render_live_gpu_feedback.py','verified_budget_feedback.py']})
    (args.output/'01-真实GPU父反馈与像素交付完整记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    plotter.close()


if __name__=='__main__':main()
