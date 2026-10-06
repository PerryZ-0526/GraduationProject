"""在实际短边收缩的新星形面上比较CPU/GPU全域包围盒查询，逐项核对成员。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,subprocess
from pathlib import Path
from time import perf_counter
import numpy as np


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True);parser.add_argument('--operations',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    start=perf_counter();import torch
    torch.cuda.init();torch.cuda.synchronize();cold_ms=(perf_counter()-start)*1000
    d=np.load(args.data);v,f=d['vertices'],d['faces'].copy();live=np.ones(len(f),dtype=bool)
    operations=json.loads(args.operations.read_text(encoding='utf-8'))
    selected=next(row for row in operations if row['budget_ms']==100)['operations'];queries=[];snapshots=[]
    for op in selected:
        a,b,c=(v[f[:,k]] for k in range(3));low=np.minimum(np.minimum(a,b),c);high=np.maximum(np.maximum(a,b),c)
        affected=np.array(op['changed_original_faces']);other=live.copy();other[affected]=False
        proposed=f[affected].copy();proposed[proposed==op['drop']]=op['keep']
        survives=np.array([len(set(t))==3 for t in proposed]);triangles=v[proposed[survives]]
        snapshots.append((low,high,other,triangles.min(1),triangles.max(1)))
        f[affected]=proposed;live[op['removed_original_faces']]=False
    rows=[]
    def cpu(low,high,other,tl,th):
        return np.flatnonzero(other&(high[:,0]>=tl[0])&(high[:,1]>=tl[1])&(high[:,2]>=tl[2])&
            (low[:,0]<=th[0])&(low[:,1]<=th[1])&(low[:,2]<=th[2]))
    for step,(low,high,other,lows,highs) in enumerate(snapshots):
        start=perf_counter()
        dl=torch.as_tensor(low,device='cuda');dh=torch.as_tensor(high,device='cuda');do=torch.as_tensor(other,device='cuda')
        ql=torch.as_tensor(lows,device='cuda');qh=torch.as_tensor(highs,device='cuda');torch.cuda.synchronize()
        upload_ms=(perf_counter()-start)*1000
        def gpu():
            # 用括号覆盖跨行表达式，保持与CPU相同的六项闭区间判定。
            mask=(do[None,:]&(dh[None,:,0]>=ql[:,None,0])&(dh[None,:,1]>=ql[:,None,1])&(dh[None,:,2]>=ql[:,None,2])&
                (dl[None,:,0]<=qh[:,None,0])&(dl[None,:,1]<=qh[:,None,1])&(dl[None,:,2]<=qh[:,None,2]))
            # 返回实际候选数量，下载和同步全部计时，不用空发射时间作GPU加速结论。
            return torch.nonzero(mask,as_tuple=False).cpu().numpy()
        expected=np.array([[i,int(j)] for i,(tl,th) in enumerate(zip(lows,highs)) for j in cpu(low,high,other,tl,th)],dtype=np.int64).reshape(-1,2)
        actual=gpu();assert np.array_equal(expected,actual)
        for repeat in range(8):
            result={}
            for backend in (('cpu','gpu') if repeat%2==0 else ('gpu','cpu')):
                start=perf_counter()
                if backend=='cpu':answer=np.array([[i,int(j)] for i,(tl,th) in enumerate(zip(lows,highs)) for j in cpu(low,high,other,tl,th)],dtype=np.int64).reshape(-1,2)
                else:answer=gpu()
                result[backend+'_ms']=(perf_counter()-start)*1000;assert np.array_equal(answer,expected)
            rows.append(dict(step=step,repeat=repeat,query_triangles=len(lows),candidate_pairs=len(expected),upload_ms=upload_ms,**result))
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        data_sha256=hashlib.sha256(args.data.read_bytes()).hexdigest(),operations_sha256=hashlib.sha256(args.operations.read_bytes()).hexdigest(),
        method_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),gpu=torch.cuda.get_device_name(0),cold_torch_and_context_ms=cold_ms,
        gpu_processes=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],capture_output=True,text=True).stdout,
        all_candidate_sets_identical=True,full_embedding_not_tested=True,rows=rows)
    assert not args.output.exists();args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'groups':len(snapshots),'paired_runs':len(rows),'cold_ms':cold_ms,'cpu_median_ms':float(np.median([x['cpu_ms'] for x in rows])),'gpu_median_ms':float(np.median([x['gpu_ms'] for x in rows]))}))


if __name__=='__main__':main()
