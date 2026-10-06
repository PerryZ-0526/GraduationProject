"""变化面证书与完整EPECK检查的实际源、别名、拓扑及相交正负控制。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
import numpy as np
import trimesh
from exact_mesh_memory import ExactMeshMemory
from incremental_mesh_memory import VerifiedMesh


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    full=ExactMeshMemory();rows=[];roots=[]
    def verify(api,v,f,name):
        before=api.handle;x=api.check(v,f,advance=False);y=full.audit(v,f)
        assert api.handle==before
        keys=['topology_valid','closed','embedded_closed','self_intersection_pairs','exact_degenerate_faces']
        if not x['topology_valid']:keys=['topology_valid','embedded_closed']
        assert all(x[k]==y[k] for k in keys),(name,x,y)
        rows.append(dict(name=name,incremental=x,full=y));print(name,x['embedded_closed'],round(x['total_elapsed_ms'],3),flush=True)
    d=np.load(args.source/'raw.npz');api=VerifiedMesh()
    roots.append(api.check(d['parent_vertices'],d['parent_faces'],advance=True));assert roots[-1]['embedded_closed']
    verify(api,d['vertices'],d['faces'],'实际第二刀原源')
    for name in ['native_repaired_20','native_repaired_50','native_repaired_100','native_repaired_200']:
        m=trimesh.load(args.source/(name+'.obj'),process=False);verify(api,np.asarray(m.vertices),np.asarray(m.faces),name)
    # 失败源不能替换父证书；合法恢复后仍能核查同一父链下一帧。
    handle=api.handle;bad=api.check(d['vertices'],d['faces'],advance=True)
    assert not bad['advanced'] and api.handle==handle
    api.close()
    for kind in ['box','sphere','two_boxes']:
        mesh=trimesh.creation.icosphere(subdivisions=1) if kind=='sphere' else trimesh.creation.box()
        if kind=='two_boxes':
            other=mesh.copy();other.apply_translation([3,0,0]);mesh=trimesh.util.concatenate([mesh,other])
        v=np.asarray(mesh.vertices);f=np.asarray(mesh.faces);api=VerifiedMesh()
        roots.append(api.check(v,f,advance=True));assert roots[-1]['embedded_closed']
        verify(api,v,f,kind+'_恒等')
        verify(api,v,f[::-1],kind+'_面重排')
        verify(api,v[::-1],len(v)-1-f,kind+'_顶点重排')
        # 无引用别名使相关旧面保守重检，不能凭坐标相同就继承共享顶点身份。
        verify(api,np.vstack((v,v[0])),f,kind+'_同坐标别名')
        moved=v.copy();moved[0]+=[.025,.03,.04];verify(api,moved,f,kind+'_小位移')
        moved=v.copy();moved[0]=v.mean(0)+[4,.25,.3];verify(api,moved,f,kind+'_大位移')
        verify(api,v,f[:-1],kind+'_缺面')
        verify(api,v,np.vstack((f,f[0])),kind+'_重复面')
        reverse=f.copy();reverse[0]=reverse[0,::-1];verify(api,v,reverse,kind+'_单面反向')
        if kind=='two_boxes':
            moved=v.copy();moved[len(v)//2:,0]-=2.75;verify(api,moved,f,'双闭壳交叠')
            moved=v.copy();moved[len(v)//2:,0]-=3;verify(api,moved,f,'双闭壳完全重合')
        api.close()
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),all_decisions_identical=True,
        controls=len(rows),roots=roots,rows=rows,
        method_sha256={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ['incremental_mesh_memory.cpp','incremental_mesh_memory.py','exact_mesh_memory.cpp']},
        source_sha256=hashlib.sha256((args.source/'raw.npz').read_bytes()).hexdigest())
    assert not args.output.exists();args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
