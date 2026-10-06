"""完整报告预算越界、准备费用、质量和GPU真实评分，不冒充在线整链。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter
import numpy as np
from budget_flip import BudgetFlipState,CpuScorer,TorchScorer,pair_triangles,triangle_metrics
from local_guard import LocalGuard


def quality(v,f,minimum_area_mm2=1e-12):
    # 默认保留历史报表；正面积版本显式包含合法极小面，不把它们从小角占比分母中抹掉。
    angle,area=triangle_metrics(v[f]);valid=np.isfinite(angle)&np.isfinite(area)&(area>minimum_area_mm2)
    result=dict(faces=len(f),invalid=int((~valid).sum()))
    # 全部面无效时面积占比没有定义，明确留空，不能产生NaN或称质量合格。
    valid_area=area[valid].sum()
    for t in (10,5,1):
        selected=valid&(angle<t)
        result[str(t)]=dict(count=int(selected.sum()),fraction=float(selected.sum()/len(f)),area_fraction=float(area[selected].sum()/valid_area) if valid_area>0 else None)
    return result


def save_obj(path,v,f):
    with path.open('w',encoding='utf-8') as stream:
        for p in v:stream.write('v '+' '.join(format(float(x),'.17g') for x in p)+'\n')
        for p in f:stream.write('f '+' '.join(str(int(x)+1) for x in p)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--backend',choices=('cpu','cuda'),required=True)
    parser.add_argument('--checker')
    args=parser.parse_args()
    root=args.root;manifest=json.loads((root/'02-输入与研究预算冻结.json').read_text(encoding='utf-8'))
    out=root/args.backend;out.mkdir(exist_ok=False)
    rows=[];controls=[];sources=[];gpu_observations=[]
    def save(status):
        p=out/'01-完整预算与保存对象记录.json'
        report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status=status,backend=args.backend,
            method_sha256=hashlib.sha256(Path(__file__).with_name('budget_flip.py').read_bytes()).hexdigest(),benchmark_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),manifest_sha256=hashlib.sha256((root/'02-输入与研究预算冻结.json').read_bytes()).hexdigest(),controls=controls,sources=sources,gpu_observations=gpu_observations,rows=rows)
        temporary=p.with_suffix('.tmp');temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(p)
    for case in manifest['cases']:
        # Windows冻结清单可在Linux执行，路径分隔符转换不改输入及摘要。
        path=root/case['file'].replace('\\','/');assert hashlib.sha256(path.read_bytes()).hexdigest()==case['sha256']
        data=np.load(path);v,f,bits,active=[data[k] for k in ('vertices','faces','bits','active')]
        before=quality(v,f)
        if args.checker:
            source_path=out/f'{case["id"]}_source.obj';save_obj(source_path,v,f)
            audit=subprocess.run([args.checker,str(source_path)],capture_output=True,text=True,timeout=120)
            sources.append(dict(case=case['id'],returncode=audit.returncode,stdout=audit.stdout,stderr=audit.stderr))
        if args.backend=='cuda':
            gpu_observations.append(dict(case=case['id'],processes=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()))
        # 核评分对拍与计时独立；实际四顶点输入保持FP64，不用降精度换取收益。
        if args.backend=='cuda':
            state=BudgetFlipState(v,f,bits,active,'cpu')
            pairs=[state._candidate(e) for e in state.queue]
            quads=np.array([x[2] for x in pairs if x is not None][:128],dtype=np.int64)
            if len(quads):
                cpu=CpuScorer(v);gpu=TorchScorer(v)
                a,b=cpu.score(quads),gpu.score(quads)
                control=dict(case=case['id'],pairs=len(quads),angle_max_abs=float(np.max(np.abs(a[0]-b[0]))),area_max_abs=float(np.max(np.abs(a[1]-b[1]))),
                    passed=bool(np.allclose(a[0],b[0],rtol=1e-6,atol=1e-5) and np.allclose(a[1],b[1],rtol=1e-12,atol=1e-12)))
                controls.append(control)
                if not control['passed']:save('blocked_by_gpu_score_control');raise RuntimeError('GPU质量评分与CPU不一致')
        for round_id in range(manifest['protocol']['rounds']):
            for budget in manifest['protocol']['budgets_ms']:
                # 近共面变体仍查完整局部相交关系；误差预算来自冻结清单。
                factory=(lambda v,f:LocalGuard(v,f,manifest['protocol']['local_error_mm'])) if manifest['protocol'].get('guard')=='near' else None
                state=BudgetFlipState(v,f,bits,active,args.backend,guard_factory=factory)
                record=state.maintain(budget,max_flips=manifest['protocol']['max_flips'])
                record.update(case=case['id'],name=case['name'],round=round_id,preparation_ms=state.preparation_ms,
                    prepared_and_step_ms=state.preparation_ms+record['elapsed_ms'],vertices_unchanged=bool(np.array_equal(state.vertices,v)),
                    outside_faces_unchanged=bool(np.array_equal(state.faces[~active],f[~active])),labels_unchanged=bool(np.array_equal(state.bits,bits)),before=before,after=quality(state.vertices,state.faces))
                record['local_error_upper_sum_mm']=float(np.nextafter(sum(op['geometry']['error_upper_mm'] for op in record['operations']),np.inf)) if record['operations'] else 0.0
                if round_id==0:
                    target=out/f'{case["id"]}_{budget}ms.obj';save_obj(target,state.vertices,state.faces)
                    record['output']=target.name;record['sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
                    if args.checker:
                        audit=subprocess.run([args.checker,str(target)],capture_output=True,text=True,timeout=120)
                        record['embedding']=dict(returncode=audit.returncode,stdout=audit.stdout,stderr=audit.stderr)
                rows.append(record);save('running')
        print(case['id'],args.backend,'complete',flush=True)
    save('completed_with_recorded_outcomes')


if __name__=='__main__':main()
