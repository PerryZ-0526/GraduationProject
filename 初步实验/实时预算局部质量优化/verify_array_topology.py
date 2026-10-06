"""核对半边数组的面排序、边约束、顶点多环、别名及非法数组，与原证书和完整检查对拍。"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import itertools
import json
import numpy as np
import trimesh
from exact_mesh_memory import ExactMeshMemory
from incremental_mesh_memory import VerifiedMesh


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    root=parser.parse_args().root.resolve()
    spec=importlib.util.spec_from_file_location('array_topology_reference',root/'reference_workers/incremental_mesh_memory.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    full=ExactMeshMemory();rows=[]
    tet_v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
    tet_f=np.array([[0,1,2],[1,0,3],[2,1,3],[0,2,3]],dtype=np.int64)
    cases=[('四面体排序'+str(i),tet_v,tet_f[list(order)]) for i,order in enumerate(itertools.permutations(range(4)))]
    sphere=trimesh.creation.icosphere(subdivisions=1)
    sv,sf=np.asarray(sphere.vertices),np.asarray(sphere.faces)
    rng=np.random.default_rng(2026100607)
    cases += [('球面随机排序'+str(i),sv,sf[rng.permutation(len(sf))]) for i in range(24)]
    # 两闭壳共享同一顶点时，边全部成对仍不能作为单一流形顶点放行。
    pinch_v=np.vstack((tet_v,-tet_v[1:]))
    pinch_f=np.vstack((tet_f,np.array([0,4,5,6])[tet_f]))
    cases += [('双闭壳顶点多环'+str(i),pinch_v,pinch_f[rng.permutation(len(pinch_f))]) for i in range(4)]
    cases += [('开放边界',tet_v,tet_f[:-1]),('同向重复面',tet_v,np.vstack((tet_f,tet_f[0]))),
              ('反向重复面',tet_v,np.vstack((tet_f,tet_f[0,::-1]))),
              ('重复顶点三角形',tet_v,np.vstack((tet_f,[0,0,1]))),
              ('无引用固定点',np.vstack((tet_v,[3.,3.,3.])),tet_f),
              ('同坐标无引用别名',np.vstack((tet_v,tet_v[0])),tet_f)]
    # 同一根网格认证所有转换，拒绝对象不推进；结果及实际数组摘要逐项保存。
    old,new=module.VerifiedMesh(),VerifiedMesh()
    assert old.check(tet_v,tet_f,True)['embedded_closed'] and new.check(tet_v,tet_f,True)['embedded_closed']
    keys=['topology_valid','closed','embedded_closed','self_intersection_pairs','exact_degenerate_faces']
    for name,v,f in cases:
        before_old,before_new=old.handle,new.handle
        a,b,c=old.check(v,f),new.check(v,f),full.audit(v,f)
        selected=keys if a['topology_valid'] and b['topology_valid'] else ['topology_valid','embedded_closed']
        assert all(a[k]==b[k]==c[k] for k in selected),(name,a,b,c)
        assert old.handle==before_old and new.handle==before_new
        rows.append(dict(name=name,reference=a,array=b,full=c,
            vertices_sha256=hashlib.sha256(v.tobytes()).hexdigest(),faces_sha256=hashlib.sha256(f.tobytes()).hexdigest()))
    errors=[]
    for name,v,f in [('负编号',tet_v,np.array([[-1,1,2]])),('超界编号',tet_v,np.array([[0,1,4]])),
                     ('非有限坐标',np.array([[np.inf,0.,0.]]),np.array([[0,0,0]]))]:
        rejected=[]
        for api in (old,new):
            before=api.handle
            try:api.check(v,f,True)
            except RuntimeError:rejected.append(True)
            else:rejected.append(False)
            assert api.handle==before
        assert all(rejected);errors.append(dict(name=name,rejected=rejected))
    old.close();new.close()
    target=root/'07-数组拓扑排序多环与非法输入控制.json';assert not target.exists()
    report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        status='completed',controls=len(rows),error_controls=len(errors),all_decisions_identical=True,rows=rows,errors=errors,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(controls=len(rows),error_controls=len(errors),all_decisions_identical=True)),flush=True)


if __name__=='__main__':main()
