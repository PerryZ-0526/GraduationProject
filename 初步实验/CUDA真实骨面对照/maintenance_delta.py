"""变更域维护对照：复用同一工具与无维护分支，失败后不继续回灌。"""
import argparse
from pathlib import Path
from datetime import datetime,timezone,timedelta
from time import perf_counter
import json
import trimesh
from coverage_baseline import boolean,maintained,diagnose,distances
from run_comparison import face_keys,export_double


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    args=parser.parse_args()
    baseline=json.loads((args.source/'results.json').read_text(encoding='utf-8'))
    folder=args.source/('delta_'+datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S'))
    folder.mkdir()
    initial=args.source/'initial.obj'
    keys=set(face_keys(trimesh.load(initial,force='mesh',process=False)))
    result=dict(status='running',source=str(args.source),plan_sha256=baseline['plan_sha256'],runs={})
    def save():
        (folder/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        for edge in [.4,.6]:
            previous=initial
            rows=[]
            result['runs'][str(edge)]=rows
            for item in baseline['plan']:
                step=item['step']
                row=dict(step=step,accepted=False)
                rows.append(row)
                started=perf_counter()
                try:
                    tool=args.source/f'tool_{step}.obj'
                    raw_path=args.source/f'raw_{step}.obj'
                    if not tool.exists() or not raw_path.exists():
                        raise RuntimeError('累计无维护参照未完成此段，停止，不跳过缺失参照')
                    raw=trimesh.load(raw_path,force='mesh',process=False)
                    proposed=raw if step==1 else boolean(previous,tool,folder/f'input_{edge}_{step}.obj')
                    output=maintained(proposed,item,edge,original_keys=keys)
                    path=folder/f'maint_{edge}_{step}.obj'
                    path.write_text(export_double(output),encoding='utf-8')
                    row.update(diagnose(output,keys))
                    row['sampled_drift']=distances(output,raw)
                    row['accepted']=bool(row['quality_gate'] and max(d['max'] for d in row['sampled_drift'])<=.075)
                    previous=path
                except Exception as exc:
                    row['error']=str(exc)
                row['elapsed_ms']=(perf_counter()-started)*1000
                save()
                print('delta',edge,step,row['accepted'],row.get('changed'),flush=True)
                if not row['accepted']:
                    break
        result['status']='completed'
    finally:
        save()
        print(folder,flush=True)


if __name__=='__main__':
    main()
