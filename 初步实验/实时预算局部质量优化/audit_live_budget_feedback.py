"""复核实际显示数组、真实工具前缀和父链，封存本次方法与动态库。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,shutil
from pathlib import Path
import numpy as np
from benchmark import quality
from exact_mesh_memory import ExactMeshMemory


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--ct-record',type=Path,required=True);args=p.parse_args()
    sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    display_path=args.root/'01-实际切削数组交付渲染与全量复审.json'
    run_path=args.root/'实际实时父反馈/01-真实父反馈四预算完整记录.json'
    display=json.loads(display_path.read_text(encoding='utf-8'));run=json.loads(run_path.read_text(encoding='utf-8'))
    ct=json.loads(args.ct_record.read_text(encoding='utf-8'))
    assert display['status']==run['status']=='completed' and display['real_computation_process_exit_code']==0
    assert sha(args.ct_record)==display['source_record_sha256'] and run['live_array_publication']
    assert display['rendered_count']==len(display['frames'])==len(display['audits'])==16 and len(run['routes'])==1
    route=run['routes'][0];assert route['status']=='completed' and route['valid_published']==len(route['events'])==16
    assert route['budget_ms']==display['budget_ms'] and route['root_check']['embedded_closed']
    initial=ct['routes'][0]['events'][0]
    assert sha(initial['parent_path'])==initial['parent_sha256']==run['initial_sha256']
    full=ExactMeshMemory();parent=run['initial_sha256'];rows=[]
    for index,(event,frame,old_audit,tool) in enumerate(zip(route['events'],display['frames'],display['audits'],ct['routes'][0]['events'])):
        assert event['step']==frame['step']==old_audit['step']==index and event['status']=='published_verified'
        assert event['parent_sha256']==parent and sha(tool['tool_path'])==tool['tool_sha256']==event['tool_sha256']==run['tool_sha256'][index]
        assert event['source_check']['embedded_closed']
        if event['final_check'] is not None:assert event['final_check']['embedded_closed']
        path=args.root/f'e{index:02d}_实际显示数组.npz'
        with np.load(path) as data:v,f,bits=[data[k] for k in ('vertices','faces','bits')]
        # 数组摘要使用在线交付的二进制顺序，初态使用原OBJ摘要，后续只认上一帧实际数组。
        h=hashlib.sha256()
        for array in (v,f,bits):h.update(memoryview(np.ascontiguousarray(array)).cast('B'))
        parent=h.hexdigest()
        assert parent==event['output_array_sha256']==frame['output_array_sha256']==old_audit['output_array_sha256']
        assert len(bits)==len(f) and set(np.unique(bits)).issubset({1,2,3})
        check=full.audit(v,f);assert check['embedded_closed']
        assert frame['maintenance_ms']==event['maintenance_total_ms'] and frame['budget_overrun']==(frame['maintenance_ms']>display['budget_ms'])
        rows.append(dict(step=index,file=str(path),file_sha256=sha(path),array_sha256=parent,check=check,quality=quality(v,f,0)))
    stats={}
    for key in ('maintenance_ms','render_ms','cut_to_vtk_render_return_ms'):
        a=np.array([frame[key] for frame in display['frames']]);stats[key]=dict(mean=float(a.mean()),p95=float(np.percentile(a,95)),max=float(a.max()))
    a=np.asarray(display['heartbeat_ms']);stats['heartbeat_ms']=dict(mean=float(a.mean()),p95=float(np.percentile(a,95)),max=float(a.max()))
    here=Path(__file__).parent;frozen=args.root/'实际方法副本';frozen.mkdir(exist_ok=False);files=[]
    # 先核对运行中登记的方法摘要，不能把后来改过的源码封存为实际执行版本。
    for name,expected in {**run['method_sha256'],**display['method_sha256']}.items():assert sha(here/name)==expected
    paths=list(here.glob('*.py'))+list(here.glob('*.cpp'))+list((here/'本机内存布尔编译').glob('CMakeLists.txt'))
    workspace=here.parents[1]
    paths+=list((workspace/'tmp/实时预算内存布尔编译/Release').glob('*.dll'))
    paths+=[workspace/'tmp/实时预算Geogram本机编译/bin/Release/geogram.dll']
    for path in paths:
        target=frozen/path.name;assert not target.exists();shutil.copy2(path,target);assert sha(target)==sha(path)
        files.append(dict(original=str(path),frozen=str(target),sha256=sha(target)))
    result=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',
        display_record_sha256=sha(display_path),feedback_record_sha256=sha(run_path),all_saved_display_arrays_embedded=True,
        complete_array_parent_chain=True,tool_prefix_verified=True,rows=rows,statistics=stats,method_files=files,
        quality_flips=sum(e['maintenance']['accepted'] if e['maintenance'] else 0 for e in route['events']),
        source_arrays_not_saved_in_live_run=True,source_quality_gain_not_independently_remeasured=True,
        scope='已见CT16真实计算与离屏VTK像素交付Qt；未测OS呈现、临床交互或连续上万次更新')
    output=args.root/'04-显示数组输入父链与方法封存复审.json';assert not output.exists()
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],frames=len(rows),method_files=len(files),statistics=stats),ensure_ascii=False))


if __name__=='__main__':main()
