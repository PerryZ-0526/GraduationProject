"""同一实际父链交错核对新旧源证书，包含质量翻边后的缓存继承。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np
from incremental_mesh_memory import VerifiedMesh
from exact_mesh_memory import ExactMeshMemory


def load_obj(path):
    # 按原文件保留全部顶点与原索引，不能经通用读取器清理后比较证书。
    v=[];f=[]
    for line in Path(path).read_text().splitlines():
        if line.startswith('v '):v.append([float(x) for x in line.split()[1:]])
        elif line.startswith('f '):f.append([int(x)-1 for x in line.split()[1:]])
    return np.asarray(v),np.asarray(f,dtype=np.int64)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--batch',type=Path,required=True);p.add_argument('--initial',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();module_path=root/'reference_workers/incremental_mesh_memory.py'
    spec=importlib.util.spec_from_file_location('original_cached_pair_reference',module_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    reference=module.VerifiedMesh;full=ExactMeshMemory();sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    record=json.loads((args.batch/'01-真实父反馈四预算完整记录.json').read_text());assert record['status']=='completed'
    iv,iff=load_obj(args.initial);rows=[];bindings=[]
    keys=['root_full_audit','topology_valid','closed','embedded_closed','self_intersection_pairs','exact_degenerate_faces',
        'inherited_faces','exact_pairs_checked','unchanged_pairs_inherited','advanced']
    for route in record['routes']:
        if route['budget_ms'] not in [100,200]:continue
        assert route['valid_published']==16
        inputs=[]
        for e in route['events']:
            sv,sf=load_obj(e['source_path']);v,f=load_obj(e['output_path']);np.testing.assert_array_equal(sv,v)
            a,b=full.audit(sv,sf),full.audit(v,f);assert a['embedded_closed'] and b['embedded_closed']
            ops=(e.get('maintenance') or {}).get('operations',[]) if e.get('final_check') and e['final_check']['embedded_closed'] else []
            inputs.append((e,sv,sf,f,ops))
            bindings.append(dict(budget=route['budget_ms'],step=e['step'],source_sha256=sha(e['source_path']),
                output_sha256=sha(e['output_path']),source_full=a,output_full=b))
        for repeat in range(3):
            old,new=reference(),VerifiedMesh();assert old.check(iv,iff,True)['embedded_closed'] and new.check(iv,iff,True)['embedded_closed']
            for e,v,sf,f,ops in inputs:
                # 只改变执行先后，不改变实际父、源、输出或操作记录。
                if repeat%2==0:a=old.check(v,sf,True);b=new.check(v,sf,True)
                else:b=new.check(v,sf,True);a=old.check(v,sf,True)
                assert all(a[k]==b[k] for k in keys),(route['budget_ms'],e['step'],a,b)
                if repeat%2==0:x=old.check_flips(v,f,ops);y=new.check_flips(v,f,ops)
                else:y=new.check_flips(v,f,ops);x=old.check_flips(v,f,ops)
                assert all(x[k]==y[k] for k in ['embedded_closed','advanced','verified_operations','exact_pairs_checked','rejection_code']),(x,y)
                # 翻边之后的下一次继承必须与实际父缓存相符，父指针保持不变。
                oh,nh=old.handle,new.handle;px,py=old.check(v,f),new.check(v,f)
                assert old.handle==oh and new.handle==nh and all(px[k]==py[k] for k in keys)
                rows.append(dict(budget=route['budget_ms'],step=e['step'],repeat=repeat,
                    reference=a,cached=b,reference_flips=x,cached_flips=y,reference_identity=px,cached_identity=py))
            old.close();new.close()
    assert len(rows)==96
    result=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',pairs=len(rows),
        all_decisions_counters_and_parent_transitions_identical=True,bindings=bindings,rows=rows,
        method_sha256={name:sha(root/'workers'/name) for name in ['incremental_mesh_memory.cpp','incremental_mesh_memory.py',
            'libincremental_mesh_memory.so','verify_cached_source_certificate.py']},
        reference_library_sha256=sha(root/'reference_workers/libincremental_mesh_memory.so'),
        scope='实际保存父链同源组件交错对拍，所有新旧相交对计数相同；预算与显示另用完整链验证')
    target=root/'02-缓存精确源证书九十六配对完整核对.json';assert not target.exists()
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(dict(pairs=len(rows),reference_median_ms=float(np.median([r['reference']['total_elapsed_ms'] for r in rows])),
        cached_median_ms=float(np.median([r['cached']['total_elapsed_ms'] for r in rows])))))


if __name__=='__main__':main()
