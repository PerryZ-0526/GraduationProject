"""从本机完整归档核对拒绝源拓扑，并绘制真实输入队列延迟与完整分母。"""
import argparse
from datetime import datetime, timezone, timedelta
import io
import json
from pathlib import Path
import zipfile
import numpy as np


def topology(vertices,faces):
    edges=np.vstack((faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]))
    keys=np.sort(edges,axis=1);_,counts=np.unique(keys,axis=0,return_counts=True)
    _,face_counts=np.unique(np.sort(faces,axis=1),axis=0,return_counts=True)
    points=vertices[faces];area=np.linalg.norm(np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]),axis=1)/2
    return dict(vertices=len(vertices),faces=len(faces),boundary_edges=int((counts==1).sum()),
        edges_with_more_than_two_faces=int((counts>2).sum()),duplicate_unoriented_face_groups=int((face_counts>1).sum()),
        repeated_index_faces=int(np.any(np.diff(np.sort(faces,axis=1),axis=1)==0,axis=1).sum()),
        fp64_nonpositive_or_nonfinite_area_faces=int((~np.isfinite(area)|(area<=0)).sum()),
        min_positive_fp64_area_mm2=float(area[area>0].min()) if np.any(area>0) else None)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True)
    p.add_argument('--diagnose-only',action='store_true');args=p.parse_args()
    records=[]
    with zipfile.ZipFile(args.folder/'11-常驻长轨迹完整执行与复审证据.zip') as archive:
        manifest=json.loads(archive.read('02-常驻长序列完整记录.json'))
        for run in manifest['runs']:
            stem=Path(run['output']).name;ledger=json.loads(archive.read(stem+'/01-真实父反馈四预算完整记录.json'))
            for event in ledger['routes'][0]['events']:
                if event['status']!='source_rejected':continue
                shapes={}
                for kind in ('raw','source'):
                    with np.load(io.BytesIO(archive.read(stem+f'/e{event["step"]:03d}_{kind}.npz'))) as data:
                        shapes[kind]=topology(data['vertices'],data['faces'])
                repair=event.get('repair') or {}
                records.append(dict(route=run['route'],reference=run['reference'],step=event['step']+1,
                    error=event.get('error'),source_check=event.get('source_check'),raw_and_repaired_topology=shapes,
                    repair_operations=len(repair.get('operations',[])),repair_elapsed_ms=repair.get('total_elapsed_ms')))
    path=args.folder/'17-实际拒绝源拓扑归因.json'
    path.write_text(json.dumps(dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),records=records),ensure_ascii=False,indent=2),encoding='utf-8')
    if args.diagnose_only:
        print(json.dumps(dict(diagnosed_rejections=len(records),output=str(path)),ensure_ascii=False));return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    live=json.loads((args.folder/'14-真实输入队列与GPU像素完整记录.json').read_text(encoding='utf-8'))
    fig,axes=plt.subplots(1,3,figsize=(13,3.6))
    for run in live['runs']:
        x=[frame['step']+1 for frame in run['frames']];label=f"{run['hz']} events/s"
        axes[0].plot(x,[f['input_to_pixels_ms'] for f in run['frames']],label=label)
        axes[1].plot(x,[f['waiting_ms'] for f in run['frames']],label=label)
        axes[2].bar(str(run['hz']),run['published'],color='#2e8b75')
        axes[2].bar(str(run['hz']),run['planned_events']-run['published'],bottom=run['published'],color='#dedede')
    axes[0].set_title('Actual input to GPU pixels');axes[1].set_title('Actual queue waiting')
    axes[2].set_title('Published / full planned scope')
    for axis in axes[:2]:axis.set_xlabel('Cut event');axis.set_ylabel('Milliseconds');axis.legend();axis.grid(alpha=.2)
    axes[2].set_xlabel('Input events/s');axes[2].set_ylabel('Events (40 / 384 each)')
    fig.suptitle('Frozen sphere development input; first rejection at event 41; no clinical guarantee')
    fig.tight_layout();folder=args.folder/'18-真实输入队列延迟统计图';folder.mkdir(exist_ok=False)
    fig.savefig(folder/'01-实际像素延迟与完整计划分母.png',dpi=180)
    fig.savefig(folder/'01-实际像素延迟与完整计划分母.pdf');plt.close(fig)
    print(json.dumps(dict(diagnosed_rejections=len(records),live_frames=sum(len(r['frames']) for r in live['runs']),output=str(path)),ensure_ascii=False))


if __name__=='__main__':main()
