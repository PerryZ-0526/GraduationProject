"""原384事件完整批反馈与真实生产队列；距离只统计，不截断合法父链。"""
import argparse,hashlib,json,sys,threading,queue
from datetime import datetime,timezone,timedelta
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh


def now():return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def arrays_sha(arrays):
    digest=hashlib.sha256()
    for array in arrays:digest.update(memoryview(np.ascontiguousarray(array)).cast('B'))
    return digest.hexdigest()


def save(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)


def load_inputs(root,route,full):
    path=root/'inputs'/route['initial_mesh'];assert sha(path)==route['initial_mesh_sha256']
    mesh=trimesh.load(path,process=False);v,f=np.asarray(mesh.vertices),np.asarray(mesh.faces)
    assert full.audit(v,f)['embedded_closed'];tools=[];checks=[]
    for item in route['prefix_tools']:
        path=root/'inputs'/item['mesh'];assert sha(path)==item['sha256']
        mesh=trimesh.load(path,process=False);tv,tf=np.asarray(mesh.vertices),np.asarray(mesh.faces)
        check=full.audit(tv,tf);assert check['embedded_closed'];tools.append((tv,tf));checks.append(check)
    assert len(tools)==384
    return v,f,tools,checks


def percentiles(values):
    return dict(mean=float(np.mean(values)),p95=float(np.percentile(values,95)),max=float(np.max(values))) if values else None


def run_route(root,route,tools,v,f,batch_size,quality_enabled,hz=None):
    from resident_batch_engine import ResidentBatchEngine
    label=route['id']+('_candidate' if quality_enabled else '_reference')+(f'_hz{hz:g}' if hz else '')
    folder=root/label;folder.mkdir(exist_ok=False);engine=ResidentBatchEngine(v,f,quality_enabled)
    parent_hash=arrays_sha((v,f,engine.bits));initial_hash=parent_hash
    rows=[];saved=[];frames=[];arrivals=[];incoming=queue.Queue();stop=threading.Event();thread=None
    plotter=None;actor=None;tool_actor=None;renderer=None
    if hz:
        import pyvista as pv
        plotter=pv.Plotter(off_screen=True,window_size=(1000,700));plotter.set_background('#18212b')
        def producer():
            origin=perf_counter()
            for index in range(len(tools)):
                if stop.wait(max(0,origin+index/hz-perf_counter())):break
                instant=perf_counter();arrivals.append(dict(step=index,arrival_perf_counter=instant));incoming.put((index,instant))
        thread=threading.Thread(target=producer,daemon=True);thread.start()
    origin=perf_counter();blocked=False
    try:
        for update,start in enumerate(range(0,len(tools),batch_size)):
            count=min(batch_size,len(tools)-start);event_ids=list(range(start,start+count))
            if blocked:
                # 上一次可能是计算器退出或非法源，受阻标签不能一律归为几何失败。
                rows.append(dict(update=update,event_steps=event_ids,status='blocked_by_previous_failed_update'))
                continue
            batch_arrivals=[]
            if hz:
                for expected in event_ids:
                    index,instant=incoming.get()
                    if index!=expected:raise ValueError('实际入队与原扫掠事件顺序不一致')
                    batch_arrivals.append(instant)
            started=perf_counter();detail,arrays=engine.step(tools[start:start+count]);ready=perf_counter()
            row=dict(update=update,event_steps=event_ids,
                tool_sha256=[route['prefix_tools'][i]['sha256'] for i in event_ids],
                parent_array_sha256=parent_hash,status=('published_verified' if detail['published'] else
                    'boolean_execution_failed' if detail.get('failed_stage')=='boolean' else 'source_rejected'),**detail)
            if detail['published']:
                v,f,bits=arrays['output'];parent_hash=arrays_sha((v,f,bits));row['output_array_sha256']=parent_hash
                if hz:
                    def poly(av,af):return pv.PolyData(av,np.column_stack((np.full(len(af),3),af)).ravel())
                    if actor is not None:plotter.remove_actor(actor,render=False)
                    if tool_actor is not None:plotter.remove_actor(tool_actor,render=False)
                    actor=plotter.add_mesh(poly(v,f),color='#ead7bb',show_edges=True,reset_camera=not frames,render=False)
                    tv,tf=tools[start+count-1]
                    tool_actor=plotter.add_mesh(poly(tv,tf),color='#4ed9cb',opacity=.25,reset_camera=False,render=False)
                    plotter.reset_camera_clipping_range()
                    if not frames:plotter.show(auto_close=False,interactive=False)
                    else:plotter.render()
                    pixels=plotter.screenshot(return_img=True);displayed=perf_counter()
                    if pixels.shape[:2]!=(700,1000) or int(pixels.max())-int(pixels.min())<=24:raise ValueError('实际批反馈帧缓冲为空')
                    if renderer is None:
                        renderer=plotter.render_window.ReportCapabilities()
                        if 'NVIDIA' not in renderer:raise ValueError('未确认NVIDIA渲染器')
                    row['input_timing']=[dict(step=index,input_to_array_ms=(ready-instant)*1000,
                        input_to_pixels_ms=(displayed-instant)*1000,waiting_ms=(started-instant)*1000)
                        for index,instant in zip(event_ids,batch_arrivals)]
                    row['active_service_to_array_ms']=(ready-started)*1000
                    row['active_service_to_pixels_ms']=(displayed-started)*1000
                    row['queue_depth_after_display']=incoming.qsize()
                    frames.append((update,pixels.copy(),hashlib.sha256(pixels.tobytes()).hexdigest()))
                else:row['online_array_ready_ms']=(ready-started)*1000
            else:
                blocked=True;stop.set()
                row['first_rejection_event_range']=[start+1,start+count]
            # 每次交付后立即保存实际检查对象，下一次原生崩溃不能抹掉已发布父链。
            # 数组服务计时不含文件保存；真实队列仍包含这些持久化工作造成的等待。
            for kind,values in arrays.items():
                if values is None:continue
                path=folder/f'b{update:03d}_{kind}.npz';temporary=path.with_suffix('.tmp')
                with temporary.open('xb') as stream:np.savez(stream,vertices=values[0],faces=values[1],bits=values[2])
                temporary.replace(path)
                saved.append(dict(update=update,kind=kind,path=str(path.relative_to(root)),file_sha256=sha(path),array_sha256=arrays_sha(values)))
            save(folder/'02-实际保存清单.json',saved)
            rows.append(row)
            with (folder/'01-逐批原始记录.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps(dict(run=label,update=update+1,events=[start+1,start+count],status=row['status'],
                service_ms=round(detail['service_ms'],3),oldest_input_to_pixels_ms=round(row['input_timing'][0]['input_to_pixels_ms'],3) if hz and detail['published'] else None)),flush=True)
    finally:
        runtime_ms=(perf_counter()-origin)*1000;stop.set()
        if thread:thread.join(timeout=2)
        if plotter:plotter.close()
        engine.close()
    if hz:
        from PIL import Image
        for update,pixels,digest in frames:
            path=folder/f'b{update:03d}_真实GPU像素.png';Image.fromarray(pixels).save(path)
            saved.append(dict(update=update,kind='pixels',path=str(path.relative_to(root)),file_sha256=sha(path),pixels_sha256=digest))
    save(folder/'02-实际保存清单.json',saved)
    counts={status:sum(len(row['event_steps']) for row in rows if row['status']==status)
        for status in ('published_verified','source_rejected','boolean_execution_failed','blocked_by_previous_failed_update')}
    assert sum(counts.values())==len(tools)
    timings=[item for row in rows for item in row.get('input_timing',[])]
    return dict(label=label,planned_events=len(tools),planned_updates=(len(tools)+batch_size-1)//batch_size,
        event_counts=counts,published_updates=sum(row['status']=='published_verified' for row in rows),
        root_check=engine.root_check,initial_array_sha256=initial_hash,rows=rows,
        array_service_ms=percentiles([row['service_ms'] for row in rows if row['status']=='published_verified']),
        elapsed_online_ms=runtime_ms,arrivals=arrivals,arrived=len(arrivals) if hz else None,
        queued_at_stop=incoming.qsize() if hz else None,schedule_cancelled=len(tools)-len(arrivals) if hz else None,
        input_to_pixels_ms=percentiles([item['input_to_pixels_ms'] for item in timings]),
        renderer_capabilities=renderer,saved_manifest_sha256=sha(folder/'02-实际保存清单.json'))


def audit(root,report):
    from exact_mesh_memory import ExactMeshMemory
    from benchmark import quality
    full=ExactMeshMemory();audits=[];started=perf_counter()
    for run in report['runs']:
        parent=run['initial_array_sha256'];mapping={row['update']:row for row in run['rows']}
        saved=json.loads((root/run['label']/'02-实际保存清单.json').read_text(encoding='utf-8'))
        for entry in saved:
            path=root/entry['path'];assert sha(path)==entry['file_sha256']
            if entry['kind']=='pixels':continue
            with np.load(path) as data:arrays=tuple(data[k].copy() for k in ('vertices','faces','bits'))
            assert arrays_sha(arrays)==entry['array_sha256'];v,f,bits=arrays;row=mapping[entry['update']]
            check=full.audit(v,f)
            if entry['kind']=='source' and row['published']:assert check['embedded_closed']
            if entry['kind']=='output':
                assert check['embedded_closed'] and entry['array_sha256']==row['output_array_sha256']
                assert row['parent_array_sha256']==parent;parent=entry['array_sha256']
                source_path=path.with_name(path.name.replace('_output','_source'))
                with np.load(source_path) as source:assert np.array_equal(v,source['vertices'])
            audits.append(dict(run=run['label'],**entry,check=check,quality=quality(v,f,0)))
        rejected=next((row for row in run['rows'] if row['status'] in ('source_rejected','boolean_execution_failed')),None)
        if rejected:assert rejected['parent_array_sha256']==parent
    result=dict(time_beijing=now(),status='completed',arrays=audits,elapsed_ms=(perf_counter()-started)*1000,
        parent_chain_passed=True,quality_vertices_bitwise_fixed=True,geometry_policy='report_only_no_distance_stop')
    save(root/'04-实际保存数组完整精确复审.json',result)
    print(json.dumps(dict(full_audit_arrays=len(audits),elapsed_ms=result['elapsed_ms'],time_beijing=now())),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--mode',choices=['long','live'],default='long');parser.add_argument('--batch-size',type=int,default=5)
    parser.add_argument('--hz',type=float,default=5);args=parser.parse_args();root=args.root
    if not 1<=args.batch_size<=31:raise ValueError('批量工具数必须在1至31之间')
    if not np.isfinite(args.hz) or args.hz<=0:raise ValueError('输入频率必须有限且为正')
    sys.path.insert(0,str(root/'workers'))
    from exact_mesh_memory import ExactMeshMemory
    import torch
    startup=perf_counter();torch.cuda.init();torch.cuda.synchronize()
    gpu=dict(device=torch.cuda.get_device_name(0),torch_version=torch.__version__,startup_ms=(perf_counter()-startup)*1000)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'));binding=json.loads((root/'01-批量方法与依赖绑定.json').read_text(encoding='utf-8'))
    for name,digest in binding['workers'].items():assert sha(root/'workers'/name)==digest
    for library in binding['external_libraries']:assert sha(library['path'])==library['sha256']
    record=dict(time_beijing=now(),status='running',mode=args.mode,batch_size=args.batch_size,hz=args.hz if args.mode=='live' else None,
        gpu=gpu,method_binding_sha256=sha(root/'01-批量方法与依赖绑定.json'),manifest_sha256=sha(root/'manifest.json'),
        quality_budget_policy='原200ms维护预算内可选30ms最多4翻边；必要认证越时统计，不因此拒绝',
        geometry_policy='report_only_no_distance_stop',runs=[],
        scope='完整原扫掠工具；批更新分别反馈自身合法父网格；参照共享Geogram及必要修复，不是算法独立真值')
    target=root/'03-完整批量父反馈记录.json';save(target,record);full=ExactMeshMemory()
    try:
        for route in manifest['routes']:
            if args.mode=='live' and route['body']!='sphere':continue
            v,f,tools,checks=load_inputs(root,route,full)
            save(root/(route['id']+'_工具认证.json'),checks)
            for quality_enabled in ([True,False] if args.mode=='long' else [True]):
                record['runs'].append(run_route(root,route,tools,v.copy(),f.copy(),args.batch_size,quality_enabled,args.hz if args.mode=='live' else None));save(target,record)
        record.update(status='execution_completed_audit_pending',execution_finished_beijing=now());save(target,record)
        audit(root,record)
        record.update(status='completed_with_recorded_failures' if any(r['event_counts']['source_rejected'] or r['event_counts']['boolean_execution_failed'] for r in record['runs']) else 'completed',finished_beijing=now());save(target,record)
    except Exception as error:
        record.update(status='failed',error=repr(error),finished_beijing=now());save(target,record);raise


if __name__=='__main__':main()
