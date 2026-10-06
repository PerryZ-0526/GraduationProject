"""核对内存接口与同版本文件接口，并测量真实CT首刀的常驻切削耗时。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import numpy as np
import trimesh
from benchmark import save_obj,quality
from geogram_memory import GeogramMemory


def canonical(v,f,bits):
    # 作者并行执行可能改变编号；只做循环旋转和集合排序，仍保留坐标、面朝向和来源位。
    tri=v[f];rows=[]
    for points,bit in zip(tri,bits):
        rotations=[tuple(np.roll(points,-k,axis=0).ravel()) for k in range(3)]
        rows.append(min(rotations)+(int(bit),))
    return sorted(map(tuple,v)),sorted(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--ct-record',type=Path,required=True)
    parser.add_argument('--no-simplify',action='store_true')
    args=parser.parse_args();args.root.mkdir(exist_ok=False,parents=True)
    workspace=Path(__file__).resolve().parents[2]
    # Linux对照程序链接本次冻结私有库，Windows仍使用原明确文件接口位置。
    exe=(workspace/'tmp/实时预算内存布尔编译/Release/geogram_file_reference.exe'
         if sys.platform=='win32' else Path(__file__).with_name('geogram_file_reference'))
    env=dict(os.environ);env['PATH']=str(workspace/'tmp/实时预算Geogram本机编译/bin/Release')+os.pathsep+env['PATH']
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    record=json.loads(args.ct_record.read_text(encoding='utf-8'))
    event=record['routes'][0]['events'][0]
    parent,tool=Path(event['parent_path']),Path(event['tool_path'])
    assert sha(parent)==event['parent_sha256'] and sha(tool)==event['tool_sha256']
    box=trimesh.creation.box(extents=[2,2,2]);cases=[]
    for name,size,center,volume in [('不相交',2,[4,0,0],8),('重叠',2,[1,1,1],7),('内腔',1,[0,0,0],7)]:
        b=trimesh.creation.box(extents=[size]*3);b.apply_translation(center)
        cases.append((name,box,b,volume))
    cases.append(('真实CT首刀',trimesh.load(parent,process=False),trimesh.load(tool,process=False),None))
    api=GeogramMemory();rows=[]
    report={'time_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'source_record':str(args.ct_record),'source_record_sha256':sha(args.ct_record),
            'sources':{str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('geogram_memory.py'),
                Path(__file__).with_name('geogram_memory.cpp'),exe,
                exe.with_name('geogram_memory.dll' if sys.platform=='win32' else 'libgeogram_memory.so'),
                workspace/'tmp/实时预算Geogram本机编译/bin/Release/geogram.dll' if sys.platform=='win32'
                else Path(json.loads(Path(__file__).with_name('build_identity.json').read_text())['libraries'][0]['path']),parent,tool]},
            'cases':rows,'status':'running','actual_display_tested':False,'own_parent_feedback_tested':False}
    def save():
        (args.root/'01-常驻内存布尔与文件对照实际记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    for name,a,b,volume in cases:
        out=args.root/name;out.mkdir()
        av,af=np.asarray(a.vertices),np.asarray(a.faces);bv,bf=np.asarray(b.vertices),np.asarray(b.faces)
        timings=[];first=None;repeated_matches=[]
        for iteration in range(6):
            v,f,bits,timing=api.difference(av,af,bv,bf,no_simplify=args.no_simplify);timings.append(timing)
            current=canonical(v,f,bits)
            if first is None:first=current
            else:repeated_matches.append(current==first)
        save_obj(out/'parent.obj',av,af);save_obj(out/'tool.obj',bv,bf)
        start=perf_counter()
        command=subprocess.run([str(exe)]+(['--no-simplify'] if args.no_simplify else [])+[str(out/'parent.obj'),str(out/'tool.obj'),str(out/'file.obj'),str(out/'labels.json')],env=env,capture_output=True,text=True)
        file_ms=(perf_counter()-start)*1000
        (out/'file_stdout.txt').write_text(command.stdout,encoding='utf-8');(out/'file_stderr.txt').write_text(command.stderr,encoding='utf-8')
        assert command.returncode==0,(name,command.stderr)
        file_mesh=trimesh.load(out/'file.obj',process=False,maintain_order=True)
        file_bits=np.asarray(json.loads((out/'labels.json').read_text(encoding='utf-8'))['operand_bits'])
        # 同次顺序对拍另行记录；通过判据使用保持朝向和来源位的精确集合对拍。
        matches={'vertices':bool(np.array_equal(v,file_mesh.vertices)),'faces':bool(np.array_equal(f,file_mesh.faces)),
                 'operand_bits':bool(np.array_equal(bits,file_bits))}
        save_obj(out/'memory.obj',v,f);np.savez(out/'memory.npz',vertices=v,faces=f,bits=bits)
        result=trimesh.Trimesh(v,f,process=False);q=quality(v,f)
        row={'name':name,'input_faces':len(af),'tool_faces':len(bf),'output_faces':len(f),'timings':timings,
             'file_process_total_ms':file_ms,'exact_array_matches':matches,'quality':q,
             'exact_oriented_set_match':canonical(v,f,bits)==canonical(file_mesh.vertices,file_mesh.faces,file_bits),
             'repeated_exact_oriented_set_matches':repeated_matches,
             'watertight':bool(result.is_watertight),'volume':float(result.volume),'expected_volume':volume,
             'output_sha256':sha(out/'memory.obj'),'embedded_not_proven_by_watertight':True}
        rows.append(row);save()
        assert row['exact_oriented_set_match'] and all(repeated_matches),row
        if volume is not None:assert q['invalid']==0 and result.is_watertight and abs(result.volume-volume)<1e-12
        print(name,json.dumps({'matches':matches,'quality':q,'warm_total_ms':[x['total_ms'] for x in timings[1:]]},ensure_ascii=False),flush=True)
    # ABI错误路径必须返回错误，随后合法调用仍可运行。
    invalid_controls=[]
    for kind in ('非有限','越界'):
        v=np.array(box.vertices);f=np.array(box.faces)
        if kind=='非有限':v[0,0]=np.nan
        else:f[0,0]=len(v)
        try:api.difference(v,f,box.vertices,box.faces)
        except RuntimeError as exc:invalid_controls.append({'kind':kind,'rejected':True,'error':str(exc)})
        else:raise AssertionError('非法输入未拒绝')
    api.difference(box.vertices,box.faces,cases[0][2].vertices,cases[0][2].faces)
    report['invalid_controls']=invalid_controls;report['status']='completed_with_recorded_outcomes';save()


if __name__=='__main__':main()
