"""在真实CT准备源上对拍CPU与CUDA稳定边排序，包含传输和同步费用。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,subprocess
from pathlib import Path
from time import perf_counter
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    data=np.load(args.data);faces=data['faces'];offsets=data['offsets'];counts=data['vertex_counts']
    start=perf_counter();import torch
    torch.cuda.init();torch.cuda.synchronize();cold=(perf_counter()-start)*1000;rows=[]
    processes=lambda:subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],capture_output=True,text=True).stdout
    before_processes=processes()
    def cpu(f,n):
        a=f.ravel();b=np.roll(f,-1,axis=1).ravel();keys=np.minimum(a,b)*n+np.maximum(a,b)
        order=np.argsort(keys,kind='stable');return order,keys[order]
    def cuda(f,n):
        a=f.reshape(-1);b=torch.roll(f,-1,dims=1).reshape(-1);keys=torch.minimum(a,b)*int(n)+torch.maximum(a,b)
        order=torch.argsort(keys,stable=True)
        # 下载实际全图索引，不能只计GPU排序核发射；两个输出均与CPU逐项核对。
        return order.cpu().numpy(),keys[order].cpu().numpy()
    for case in range(len(counts)):
        f=faces[offsets[case]:offsets[case+1]];n=int(counts[case]);expected=cpu(f,n)
        start=perf_counter();resident=torch.as_tensor(f,device='cuda');torch.cuda.synchronize();upload=(perf_counter()-start)*1000
        cuda(resident,n)
        for repeat in range(6):
            order=('cpu','cuda_uploaded','cuda_resident') if repeat%2==0 else ('cuda_resident','cuda_uploaded','cpu');times={}
            for mode in order:
                start=perf_counter()
                answer=cpu(f,n) if mode=='cpu' else cuda(torch.as_tensor(f,device='cuda') if mode=='cuda_uploaded' else resident,n)
                times[mode+'_ms']=(perf_counter()-start)*1000
                assert all(np.array_equal(a,b) for a,b in zip(answer,expected)),(case,repeat,mode)
            rows.append(dict(case=case,repeat=repeat,faces=len(f),edges=3*len(f),initial_upload_ms=upload,**times))
        del resident
    medians={key:float(np.median([r[key] for r in rows])) for key in ('cpu_ms','cuda_uploaded_ms','cuda_resident_ms')}
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',all_stable_indices_identical=True,
        actual_sources=len(counts),paired_runs=len(rows),gpu=torch.cuda.get_device_name(0),cold_torch_and_context_ms=cold,
        torch_version=torch.__version__,gpu_processes_before=before_processes,gpu_processes_after=processes(),rows=rows,medians=medians,
        data_sha256=hashlib.sha256(args.data.read_bytes()).hexdigest(),method_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='同远端CPU/CUDA的实际全图边索引准备；未接入真实父反馈，不是整帧加速结论')
    assert not args.output.exists();args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(sources=len(counts),paired_runs=len(rows),medians=medians,cold_ms=cold)))


if __name__=='__main__':main()
