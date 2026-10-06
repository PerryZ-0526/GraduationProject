"""同一冻结Geogram首刀比较CPU亲和性，核对实际线程和完整输出身份。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,os,subprocess,sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ct-record',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--worker',action='store_true')
    p.add_argument('--cpus',type=int,default=0);args=p.parse_args()
    sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if args.worker:
        allowed=sorted(os.sched_getaffinity(0))
        # 必须在导入数值库和启动线程池之前限制亲和性，原版0保留实际默认范围。
        if args.cpus:os.sched_setaffinity(0,allowed[:args.cpus])
        # 远端私有构建根的脚本从相邻实际工作器加载同一冻结接口。
        if Path(__file__).with_name('workers').is_dir():sys.path.insert(0,str(Path(__file__).with_name('workers')))
        import numpy as np
        import trimesh
        from geogram_memory import GeogramMemory
        from exact_mesh_memory import ExactMeshMemory
        from verify_geogram_memory import canonical
        source=json.loads(args.ct_record.read_text());event=source['routes'][0]['events'][0]
        parent,tool=Path(event['parent_path']),Path(event['tool_path'])
        assert sha(parent)==event['parent_sha256'] and sha(tool)==event['tool_sha256']
        a=trimesh.load(parent,process=False);b=trimesh.load(tool,process=False);api=GeogramMemory();timings=[];hashes=[]
        for iteration in range(6):
            v,f,bits,timing=api.difference(a.vertices,a.faces,b.vertices,b.faces,no_simplify=True)
            timings.append(timing)
            # 编号可改变，精确坐标、面朝向和来源位集合仍须完全相同。
            cv,ct=canonical(v,f,bits)
            h=hashlib.sha256(np.asarray(cv,dtype=np.float64).tobytes()+np.asarray(ct,dtype=np.float64).tobytes()).hexdigest()
            hashes.append(h)
        check=ExactMeshMemory().audit(v,f);assert check['embedded_closed'] and len(set(hashes))==1
        args.output.mkdir(exist_ok=False);np.savez(args.output/'actual_output.npz',vertices=v,faces=f,bits=bits)
        record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',
            requested_cpus=args.cpus,affinity=sorted(os.sched_getaffinity(0)),
            thread_count=int(next(x for x in Path('/proc/self/status').read_text().splitlines() if x.startswith('Threads:')).split()[1]),
            timings=timings,output_canonical_sha256=hashes[0],full_check=check,parent_sha256=sha(parent),tool_sha256=sha(tool),
            method_sha256=sha(__file__),build_identity=json.loads(Path(sys.modules['geogram_memory'].__file__).with_name('build_identity.json').read_text()))
        (args.output/'01-实际线程与首刀切削记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(cpus=args.cpus,threads=record['thread_count'],warm_ms=[t['total_ms'] for t in timings[1:]])),flush=True)
        return
    args.output.mkdir(exist_ok=False);rows=[]
    record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',rows=rows,
        method_sha256=sha(__file__),source_record_sha256=sha(args.ct_record),scope='已见CT同一首刀，非连续反馈或GPU质量整帧证明')
    target=args.output/'01-亲和性完整交错对照.json'
    for repeat,order in enumerate([[0,4,8,16],[16,8,4,0],[4,0,16,8]]):
        for cpus in order:
            directory=args.output/f'r{repeat}_c{cpus}'
            command=[sys.executable,__file__,'--worker','--ct-record',str(args.ct_record),'--output',str(directory),'--cpus',str(cpus)]
            with (args.output/f'r{repeat}_c{cpus}.log').open('x') as stream:r=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
            assert r.returncode==0,(repeat,cpus)
            path=directory/'01-实际线程与首刀切削记录.json';row=json.loads(path.read_text());rows.append(dict(repeat=repeat,cpus=cpus,record=row,sha256=sha(path)))
            target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    record['all_output_sets_identical']=len({row['record']['output_canonical_sha256'] for row in rows})==1
    record['status']='completed';target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
