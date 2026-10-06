"""固定翻边证书与全量检查对拍，保留协议拒绝、外部碰撞及同输入配对计时。"""
import argparse,copy
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
import numpy as np
import trimesh
from exact_mesh_memory import ExactMeshMemory
from incremental_mesh_memory import VerifiedMesh


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    record=args.batch/'01-真实父反馈四预算完整记录.json';run=json.loads(record.read_text(encoding='utf-8'))
    route=next(r for r in run['routes'] if r['budget_ms']==200);full=ExactMeshMemory();rows=[];protocol=[];operation_protocol_checked=False
    def load_exact_indices(path):
        # 通用OBJ加载器会去掉无引用顶点；操作证书必须保留保存文件中的真实原索引。
        vertices=[];faces=[]
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:]])
            elif line.startswith('f '):faces.append([int(x)-1 for x in line.split()[1:]])
        return np.asarray(vertices,dtype=np.float64),np.asarray(faces,dtype=np.int64)
    for event in route['events']:
        v,f=load_exact_indices(event['source_path']);ov,out=load_exact_indices(event['output_path'])
        # 合法源直接发布时没有质量阶段，按真实零操作对拍，不补造翻边记录。
        np.testing.assert_array_equal(v,ov);ops=(event['maintenance'] or {}).get('operations',[])
        check=full.audit(v,out);assert check['embedded_closed'];pairs=[]
        for repeat in range(3):
            api=VerifiedMesh();assert api.check(v,f,advance=True)['embedded_closed']
            # 重建路径不推进源，固定翻边路径实际提交；同对象同轮配对，交错测量先后次序。
            if repeat%2==0:old=api.check(v,out);new=api.check_flips(v,out,ops)
            else:
                other=VerifiedMesh();assert other.check(v,f,advance=True)['embedded_closed']
                new=api.check_flips(v,out,ops);old=other.check(v,out);other.close()
            assert old['embedded_closed']==new['embedded_closed']==check['embedded_closed']
            assert api.check(v,out)['embedded_closed'];api.close();pairs.append(dict(repeat=repeat,rebuild=old,local=new))
        rows.append(dict(step=event['step'],operations=len(ops),full=check,pairs=pairs));print(event['step'],len(ops),new['total_elapsed_ms'],flush=True)
        # 预算策略可能首帧没有操作；协议负例必须绑定首个实际有翻边的保存对象。
        if ops and not operation_protocol_checked:
            operation_protocol_checked=True
            cases=[];bad=copy.deepcopy(ops);bad[0]['before'][0][0]=len(v);cases.append(('过期原面',v,out,bad))
            cases.append(('遗漏记录',v,out,ops[:-1]))
            bad_faces=out.copy();bad_faces[[0,1]]=bad_faces[[1,0]];cases.append(('额外面变化',v,bad_faces,ops))
            moved=v.copy();moved[0,0]=np.nextafter(moved[0,0],np.inf);cases.append(('固定点逐位变化',moved,out,ops))
            for name,cv,cf,operations in cases:
                api=VerifiedMesh();assert api.check(v,f,advance=True)['embedded_closed']
                rejected=api.check_flips(cv,cf,operations);assert not rejected['advanced']
                restored=api.check(v,f);assert restored['embedded_closed'] and restored['inherited_faces']==len(f)
                protocol.append(dict(name=name,rejected=rejected,parent_unchanged=restored));api.close()
    assert operation_protocol_checked,'本批没有实际翻边，不能冒称完成记录协议负例'
    # 用球面内的独立小闭壳构造外部障碍：旧面不相交，新对角线三角形穿过小壳。
    sphere=trimesh.creation.icosphere(subdivisions=0);v=np.asarray(sphere.vertices);f=np.asarray(sphere.faces)
    from budget_flip import BudgetFlipState
    state=BudgetFlipState(v,f,np.ones(len(f),dtype=np.uint8),np.ones(len(f),dtype=bool))
    i,j,quad=next(item for edge in state.edges if (item:=state._candidate(edge)) is not None)
    a,b,c,d=quad;after=np.array([[c,d,b],[d,c,a]],dtype=np.int64)
    obstacle=trimesh.creation.box(extents=[.03,.03,.03]);obstacle.apply_translation(v[after[0]].mean(0))
    combined=trimesh.util.concatenate([sphere,obstacle]);cv=np.asarray(combined.vertices);cf=np.asarray(combined.faces)
    op=dict(faces=[i,j],before=cf[[i,j]].tolist(),after=after.tolist());out=cf.copy();out[[i,j]]=after
    api=VerifiedMesh();root=api.check(cv,cf,advance=True);assert root['embedded_closed']
    rejected=api.check_flips(cv,out,[op]);physical=full.audit(cv,out)
    assert not rejected['advanced'] and not physical['embedded_closed'];assert api.check(cv,cf)['embedded_closed'];api.close()
    protocol.append(dict(name='远区独立闭壳新面碰撞',root=root,rejected=rejected,full_candidate=physical,parent_preserved=True))
    # 四面体任意共同边的新对角线已存在，必须按拓扑前提拒绝。
    # 显式非共面四点，避免将球面索引前四点误当成合法四面体控制。
    tet=trimesh.Trimesh(vertices=[[0,0,0],[1,0,0],[0,1,0],[0,0,1]],faces=[[0,1,2],[1,0,3],[2,1,3],[0,2,3]],process=False)
    tv=np.asarray(tet.vertices);tf=np.asarray(tet.faces);api=VerifiedMesh();assert api.check(tv,tf,advance=True)['embedded_closed']
    candidate=tf.copy();candidate[[0,1]]=[[2,3,1],[3,2,0]]
    op=dict(faces=[0,1],before=tf[[0,1]].tolist(),after=candidate[[0,1]].tolist())
    rejected=api.check_flips(tv,candidate,[op]);assert not rejected['advanced'];assert api.check(tv,tf)['embedded_closed'];api.close()
    protocol.append(dict(name='全图已有新对角线',rejected=rejected,parent_preserved=True))
    old=np.array([p['rebuild']['total_elapsed_ms'] for r in rows for p in r['pairs']]);new=np.array([p['local']['total_elapsed_ms'] for r in rows for p in r['pairs']])
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',actual_controls=len(rows),paired_runs=len(old),
        protocol_controls=len(protocol),rows=rows,protocol=protocol,rebuild_median_ms=float(np.median(old)),local_median_ms=float(np.median(new)),
        record_sha256=hashlib.sha256(record.read_bytes()).hexdigest(),
        method_sha256={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ['incremental_mesh_memory.cpp','incremental_mesh_memory.py',Path(__file__).name]},
        scope='同实际准备源与输出认证组件；非整帧加速或新患者验证')
    assert not args.output.exists();args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['rows','protocol','method_sha256']},ensure_ascii=False))


if __name__=='__main__':main()
