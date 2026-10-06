"""准确有理数区间控制、近接触及长期11同源四方法交错认证，非法源不发布。"""
from pathlib import Path
from fractions import Fraction
import ctypes as C
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import numpy as np

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_方向区间与投影源认证对照_v3')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prepared=json.loads((ROOT/'01-四方法独立编译与资产恢复.json').read_text(encoding='utf-8'))
assert prepared['status']=='completed'
for member,digest in prepared['frozen_files'].items():assert sha(ROOT/member)==digest
record=ROOT/'02-四方法准确区间与长期同源终态.json';assert not record.exists()
variants=['reference','directional','projected','combined'];factories={};rows=[];assets=[];stages=[]
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='running',
    prepared_sha256=sha(ROOT/'01-四方法独立编译与资产恢复.json'),rows=rows,assets=assets,controls=stages,
    profile_sha256=sha(__file__),resource_isolation_not_proven=True,scope='已见合法和非法源组件；非完整反馈或像素交付')


def save():
    temp=record.with_suffix('.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(record)


save()
try:
    for name in variants:
        path=ROOT/name/'incremental_mesh_memory.py';spec=importlib.util.spec_from_file_location('interval_'+name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);factories[name]=module.VerifiedMesh
    # 不以浮点参照验证浮点区间，准确和由输入binary64的有理数表示计算。
    rng=np.random.default_rng(2026100702);points=rng.integers(0,np.iinfo(np.uint64).max,size=(4000,3),dtype=np.uint64).view(np.float64)
    points=points[np.isfinite(points).all(axis=1)]
    tiny=np.nextafter(0.,1.);normal=np.finfo(np.float64).tiny;maximum=np.finfo(np.float64).max
    extremes=np.array([[maximum,maximum,0],[-maximum,-maximum,0],[maximum,-maximum,0],
        [normal,-np.nextafter(normal,np.inf),0],[tiny,normal,1],[0,0,0],[-0.,0.,tiny]])
    points=np.ascontiguousarray(np.vstack((points,extremes)))
    interval_api=factories['directional']().lib
    interval_api.get_point_direction_intervals.argtypes=[C.c_void_p,C.c_uint64,C.c_void_p,C.c_int]
    interval_api.get_point_direction_intervals.restype=None
    exact=[]
    for p in points:
        a,b,c=map(Fraction.from_float,map(float,p));exact.append([a+b,a-b,a+c,a-c,b+c,b-c])
    rounding=[]
    for mode in [0,0x100,0x200,0x300]:
        out=np.empty((len(points),12));interval_api.get_point_direction_intervals(points.ctypes.data,len(points),out.ctypes.data,mode)
        assert not np.isnan(out).any()
        for index,bounds in enumerate(out):
            for axis in range(6):
                low,high=map(float,(bounds[axis],bounds[axis+6]));value=exact[index][axis]
                assert low<=high and (low==-np.inf or Fraction.from_float(low)<=value) and (high==np.inf or value<=Fraction.from_float(high)),(index,axis,mode)
        rounding.append(dict(mode=mode,intervals=len(points)*6,output_sha256=hashlib.sha256(out.tobytes()).hexdigest()))
    np.save(ROOT/'interval_points.npy',points)
    report['interval_control']=dict(points=len(points),directions=6,rounding=rounding,all_exact_sums_enclosed=True,points_sha256=sha(ROOT/'interval_points.npy'));save()
    for name in variants:
        target=ROOT/'checks'/name;reference=target/'reference_workers';reference.mkdir(parents=True)
        for member in ['incremental_mesh_memory.py','incremental_mesh_memory.dll']:
            shutil.copyfile(ROOT/'reference'/member,reference/member)
        for script in ['verify_filtered_mesh_controls.py','verify_array_topology.py']:
            actual=ROOT/name/script;shutil.copyfile(BASE/script,actual)
            argv=[sys.executable,str(actual),'--root',str(target)]
            log=ROOT/(name+'_'+Path(script).stem+'.log')
            with log.open('x',encoding='utf-8') as stream:
                code=subprocess.run(argv,cwd=ROOT/name,env=dict(os.environ,PYTHONUTF8='1'),stdout=stream,stderr=subprocess.STDOUT).returncode
            stages.append(dict(variant=name,script=script,returncode=code,log_sha256=sha(log)));save();assert code==0,(name,script)
    previous=json.loads((ROOT/'original_profile.json').read_text(encoding='utf-8'))
    for asset in previous['assets']:
        folder=ROOT/'assets'/f"{asset['body']}_{asset['step']:03d}"
        parent=folder/Path(asset['parent_path']).name;source=folder/Path(asset['source_path']).name
        assert sha(parent)==asset['parent_sha256'] and sha(source)==asset['source_sha256']
        with np.load(parent) as d:pv,pf=d['vertices'].copy(),d['faces'].copy()
        with np.load(source) as d:v,f=d['vertices'].copy(),d['faces'].copy()
        certificates={name:factory() for name,factory in factories.items()}
        try:
            roots={name:c.check(pv,pf,True) for name,c in certificates.items()};assert all(r['embedded_closed'] for r in roots.values())
            full_result=np.zeros(8,dtype=np.int64);timings=np.zeros(4)
            full=certificates['reference'].lib.audit_arrays
            full.argtypes=[C.c_void_p,C.c_uint64,C.c_void_p,C.c_uint64,C.c_void_p,C.c_void_p];full.restype=C.c_int
            assert full(v.ctypes.data,len(v),f.ctypes.data,len(f),full_result.ctypes.data,timings.ctypes.data)==0
            assert full_result.tolist()==asset['full_result']
            keys=['topology_valid','closed','embedded_closed','self_intersection_pairs','exact_degenerate_faces','inherited_faces','exact_pairs_checked']
            for repeat in range(3):
                checks={}
                # 四方法轮换先后且不推进，每轮使用相同实际父数组；构造与释放成本不剔除。
                order=variants[repeat:]+variants[:repeat]
                for name in order:
                    cert=certificates[name];checks[name]=cert.check(v,f)
                    counts=np.zeros(2,dtype=np.int64);api=cert.lib.get_filter_counts;api.argtypes=[C.c_void_p];api.restype=None
                    api(counts.ctypes.data);checks[name]['direction_separated_pairs']=int(counts[0]);checks[name]['projection_separated_pairs']=int(counts[1])
                assert all(checks[name][key]==checks['reference'][key] for name in variants for key in keys)
                assert checks['reference']['embedded_closed']==bool(full_result[6])
                assert checks['reference']['self_intersection_pairs']==int(full_result[5]+full_result[7])
                rows.append(dict(body=asset['body'],step=asset['step'],repeat=repeat,vertices=len(v),faces=len(f),comparisons=checks))
            assets.append(dict(body=asset['body'],step=asset['step'],parent_sha256=sha(parent),source_sha256=sha(source),full_result=full_result.tolist(),full_ms=timings.tolist()))
            save();print(json.dumps(dict(body=asset['body'],step=asset['step'],reference_ms=checks['reference']['total_elapsed_ms'],
                directional_ms=checks['directional']['total_elapsed_ms'],projected_ms=checks['projected']['total_elapsed_ms'],combined_ms=checks['combined']['total_elapsed_ms'],
                pairs=checks['reference']['exact_pairs_checked'])),flush=True)
        finally:
            for c in certificates.values():c.close()
    assert len(rows)==33 and len(assets)==11
    report.update(status='completed',pairs_per_variant=33,variants=4,all_decisions_counts_and_full_results_identical=True);save()
except Exception as error:
    report.update(status='failed',error=repr(error));save();raise
print(json.dumps(dict(status='completed',pairs=33,variants=4,assets=11)),flush=True)
