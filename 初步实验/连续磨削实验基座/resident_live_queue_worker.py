"""用真实生产线程注入完整长轨迹，测输入等待、常驻更新与NVIDIA帧缓冲交付。"""
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
from time import perf_counter
import numpy as np
import pyvista as pv
from PIL import Image


ROOT=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(ROOT/'workers'))
import long_feedback as feedback
from exact_mesh_memory import ExactMeshMemory


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def now():return datetime.now(timezone(timedelta(hours=8))).isoformat()


def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)


def poly(v,f):return pv.PolyData(v,np.column_stack((np.full(len(f),3),f)).ravel())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--rates-hz',nargs='+',type=float,default=[2,5,10]);args=parser.parse_args()
    if not args.rates_hz or any(hz<=0 or not np.isfinite(hz) for hz in args.rates_hz):raise ValueError('输入频率必须有限且为正')
    output=ROOT/'live_queue';output.mkdir(exist_ok=False)
    manifest=json.loads((ROOT/'manifest.json').read_text());route=next(r for r in manifest['routes'] if r['body']=='sphere')
    input_record=ROOT/(route['id']+'_inputs.json');source=json.loads(input_record.read_text())
    total=len(source['routes'][0]['events']);runs=[]
    report=dict(time_beijing=now(),status='running',route=route['id'],planned_per_rate=total,runs=runs,
        base_binding_sha256=sha(ROOT/'01-常驻长序列运行绑定.json'),worker_sha256=sha(__file__),
        rates_hz=args.rates_hz,input_scope='真实生产线程定时送入预加载原扫掠工具，不合并、不丢弃已送达事件',
        timing_scope='实际入队到数组及离屏像素；包含等待、必要检查、局部质量和首次冷渲染；不含客户端网络和屏幕扫描呈现')
    save(output/'01-真实输入队列与GPU像素完整记录.json',report)
    original_difference=feedback.GeogramMemory.difference
    for hz in report['rates_hz']:
        folder=output/f'hz{hz}';folder.mkdir()
        incoming=queue.Queue();stop=threading.Event();begin=threading.Event();arrivals=[];current={};frames=[];snapshots=[]
        plotter=pv.Plotter(off_screen=True,window_size=(1000,700));plotter.set_background('#18212b')
        actor=None;tool_actor=None;capabilities=None
        def producer():
            begin.wait();origin=perf_counter()
            for index in range(total):
                if stop.wait(max(0,origin+index/hz-perf_counter())):break
                instant=perf_counter();incoming.put((index,instant));arrivals.append(dict(step=index,arrival_perf_counter=instant))
        thread=threading.Thread(target=producer,daemon=True);thread.start()
        def difference(api,av,af,bv,bf,**kwargs):
            # 全部初态及工具认证完成后才开始注入，不将预加载时间伪装成每刀服务时间。
            begin.set();index,instant=incoming.get();start=perf_counter()
            current.update(step=index,arrival=instant,start=start,waiting_ms=(start-instant)*1000,queue_depth=incoming.qsize())
            return original_difference(api,av,af,bv,bf,**kwargs)
        feedback.GeogramMemory.difference=difference
        def publish(v,f,bits,tv,tf,event):
            nonlocal actor,tool_actor,capabilities
            if event['step']!=current['step']:raise ValueError('实际队列顺序与磨削反馈不同')
            h=hashlib.sha256()
            for a in (v,f,bits):h.update(memoryview(np.ascontiguousarray(a)).cast('B'))
            if h.hexdigest()!=event['output_array_sha256']:raise ValueError('实时显示数组摘要不一致')
            ready=perf_counter()
            if actor is not None:plotter.remove_actor(actor,render=False)
            if tool_actor is not None:plotter.remove_actor(tool_actor,render=False)
            actor=plotter.add_mesh(poly(v,f),color='#ead7bb',show_edges=True,reset_camera=not frames,render=False)
            tool_actor=plotter.add_mesh(poly(tv,tf),color='#4ed9cb',opacity=.25,reset_camera=False,render=False)
            plotter.reset_camera_clipping_range()
            if not frames:plotter.show(auto_close=False,interactive=False)
            else:plotter.render()
            pixels=plotter.screenshot(return_img=True);end=perf_counter()
            if pixels.shape[:2]!=(700,1000) or int(pixels.max())-int(pixels.min())<=24:raise ValueError('实际帧缓冲为空')
            if capabilities is None:
                capabilities=plotter.render_window.ReportCapabilities()
                if 'NVIDIA' not in capabilities:raise ValueError('未确认NVIDIA实际渲染器')
            frame=dict(step=event['step'],waiting_ms=current['waiting_ms'],queue_depth_at_start=current['queue_depth'],
                input_to_array_ms=(ready-current['arrival'])*1000,input_to_pixels_ms=(end-current['arrival'])*1000,
                active_service_to_array_ms=(ready-current['start'])*1000,active_service_to_pixels_ms=(end-current['start'])*1000,
                maintenance_ms=event['maintenance_total_ms'],output_array_sha256=h.hexdigest(),
                pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest())
            frames.append(frame);snapshots.append((v.copy(),f.copy(),bits.copy(),pixels.copy()))
            print(json.dumps(dict(hz=hz,step=event['step']+1,input_to_pixels_ms=round(frame['input_to_pixels_ms'],3),waiting_ms=round(frame['waiting_ms'],3))),flush=True)
        # 继承长序列入口的只读诊断属性，不把拒绝源送去显示。
        publish.failure=lambda raw,source,event:stop.set()
        sys.argv=[__file__,'--ct-record',str(input_record),'--output',str(folder/'feedback'),'--budgets','200',
                  '--fixed-flip-certificate','--early-quality-return','--edge-backend','cuda','--certified-operand-pairs']
        try:feedback.main(publisher=publish)
        finally:
            stop.set();begin.set();thread.join(timeout=2);feedback.GeogramMemory.difference=original_difference
            plotter.close()
        ledger=json.loads((folder/'feedback/01-真实父反馈四预算完整记录.json').read_text())
        events=ledger['routes'][0]['events'];published=sum(e['status']=='published_verified' for e in events)
        full=ExactMeshMemory();audits=[]
        # 文件、PNG和完整全量复审都在实时注入结束后执行，原始数组逐件核对。
        for frame,(v,f,bits,pixels) in zip(frames,snapshots):
            path=folder/f'e{frame["step"]:03d}_显示数组.npz';np.savez_compressed(path,vertices=v,faces=f,bits=bits)
            image=folder/f'e{frame["step"]:03d}_真实GPU像素.png';Image.fromarray(pixels).save(image)
            check=full.audit(v,f)
            if not check['embedded_closed']:raise ValueError('实际显示数组完整精确复审失败')
            audits.append(dict(step=frame['step'],check=check,array_sha256=sha(path),png_sha256=sha(image)))
        run=dict(hz=hz,planned_events=total,published=published,arrived=len(arrivals),queued_at_stop=incoming.qsize(),
            schedule_cancelled=total-len(arrivals),first_rejection=next((e['step']+1 for e in events if e['status']=='source_rejected'),None),
            renderer_capabilities=capabilities,frames=frames,arrivals=arrivals,full_saved_audits=audits,
            mean_input_to_pixels_ms=float(np.mean([f['input_to_pixels_ms'] for f in frames])),
            p95_input_to_pixels_ms=float(np.percentile([f['input_to_pixels_ms'] for f in frames],95)),
            max_input_to_pixels_ms=max(f['input_to_pixels_ms'] for f in frames),
            max_waiting_ms=max(f['waiting_ms'] for f in frames),
            ledger_sha256=sha(folder/'feedback/01-真实父反馈四预算完整记录.json'))
        runs.append(run);save(output/'01-真实输入队列与GPU像素完整记录.json',report)
        print(json.dumps({k:v for k,v in run.items() if k not in ('frames','arrivals','full_saved_audits','renderer_capabilities')},ensure_ascii=False),flush=True)
    report.update(status='completed_with_recorded_rejections',finished_beijing=now())
    save(output/'01-真实输入队列与GPU像素完整记录.json',report)


if __name__=='__main__':main()
