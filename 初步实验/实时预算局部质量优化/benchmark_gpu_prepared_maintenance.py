"""同实际准备源CPU/CUDA邻接维护对照，保留完整输出与精确自交复审。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,subprocess
from pathlib import Path
from time import perf_counter
import numpy as np
from benchmark import quality,save_obj
from maintain_input import maintain_input
from native_guard import NativeLocalGuard,load_library


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--checker',required=True);args=p.parse_args()
    args.output.mkdir(exist_ok=False);data=np.load(args.data)
    start=perf_counter();import torch
    torch.cuda.init();torch.cuda.synchronize();cold=(perf_counter()-start)*1000;load_library();rows=[];audits=[]
    names=['benchmark_gpu_prepared_maintenance.py','gpu_edge_index.py','maintain_input.py','targeted_budget_flip.py','budget_flip.py','native_guard.py','numeric_input.py','local_guard.py','sparse_budget_flip.py','resumable_budget_flip.py']
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',rows=rows,audits=audits,
        data_sha256=sha(args.data),method_sha256={name:sha(Path(__file__).with_name(name)) for name in names},
        library_sha256=sha(Path(__file__).with_name('local_separation.so')),checker_sha256=sha(args.checker),
        cold_torch_ms=cold,budget_ms=30,max_flips=4,gpu=torch.cuda.get_device_name(0),
        gpu_processes_before=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],capture_output=True,text=True).stdout,
        scope='已见实际CT16合法准备源静态维护；未运行GPU整条切削父反馈或显示')
    def save():
        out=args.output/'01-完整CPU与CUDA准备维护记录.json';temporary=out.with_suffix('.tmp')
        temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(out)
    def audit(v,f,name):
        path=args.output/(name+'.obj');save_obj(path,v,f)
        check=subprocess.run([args.checker,str(path)],capture_output=True,text=True,timeout=120)
        assert check.returncode==0,(name,check.stderr)
        result=json.loads(check.stdout);audits.append(dict(name=name,path=str(path),sha256=sha(path),check=result))
        assert result['embedded_closed'],(name,result)
    for case in range(len(data['tool_lows'])):
        vs=slice(data['vertex_offsets'][case],data['vertex_offsets'][case+1]);fs=slice(data['face_offsets'][case],data['face_offsets'][case+1])
        v,f,bits=data['vertices'][vs],data['faces'][fs],data['bits'][fs];before=quality(v,f,0);assert before['invalid']==0
        audit(v,f,f'case{case:02d}_source')
        for repeat in range(3):
            for backend in (('cpu','cuda') if repeat%2==0 else ('cuda','cpu')):
                state,result=maintain_input(v,f,bits,data['tool_lows'][case],data['tool_highs'][case],30,
                    guard_class=NativeLocalGuard,minimum_input_area_mm2=0,max_flips=4,edge_backend=backend)
                np.testing.assert_array_equal(v,state.vertices);np.testing.assert_array_equal(bits,state.bits)
                np.testing.assert_array_equal(f[~state.active],state.faces[~state.active])
                after=quality(state.vertices,state.faces,0);assert after['invalid']==0
                assert all(after[str(t)]['count']<=before[str(t)]['count'] for t in (10,5,1))
                row=dict(case=case,repeat=repeat,edge_backend=backend,before=before,after=after,maintenance=result)
                if repeat==0:
                    audit(state.vertices,state.faces,f'case{case:02d}_{backend}')
                    path=args.output/f'case{case:02d}_{backend}.npz'
                    np.savez_compressed(path,vertices=state.vertices,faces=state.faces,bits=state.bits)
                    row.update(output=str(path),output_sha256=sha(path))
                rows.append(row);save()
        print(case,'completed',flush=True)
    report['status']='completed';report['gpu_processes_after']=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],capture_output=True,text=True).stdout
    report['summary']={backend:dict(runs=sum(r['edge_backend']==backend for r in rows),
        total_mean_ms=float(np.mean([r['maintenance']['total_elapsed_ms'] for r in rows if r['edge_backend']==backend])),
        preparation_mean_ms=float(np.mean([r['maintenance']['preparation_ms'] for r in rows if r['edge_backend']==backend])),
        accepted=sum(r['maintenance']['accepted'] for r in rows if r['edge_backend']==backend),
        budget_overruns=sum(r['maintenance']['total_budget_overrun'] for r in rows if r['edge_backend']==backend)) for backend in ('cpu','cuda')}
    save();print(json.dumps(report['summary']))


if __name__=='__main__':main()
