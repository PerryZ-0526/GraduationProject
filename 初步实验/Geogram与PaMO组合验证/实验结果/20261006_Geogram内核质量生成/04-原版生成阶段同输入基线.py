"""对十一既有开发输入实际运行原版两模式，原生阶段计时不包含传输及评价。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import shlex
import numpy as np
import trimesh

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_remote', here/'01-隔离内核研究远程入口.py')
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)
manifest_path = Path('D:/GraduationProject_切削排斥证据/20261006_自适应局部质量未见参数与同源PaMO对照/05-新参数与同源对照运行前冻结清单.json')
manifest = json.loads(manifest_path.read_text('utf8'))
output = here/'原版直接输出基线'
output.mkdir()
root = '/tmp/geogram_native_quality_20261006_01'
source = '/root/autodl-tmp/graduation_project/followup_20260928_2344/geogram_src'
lib = source+'/build/followup-linux64-gcc-dynamic/lib'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record = {'生成时间':now(), '修改时间及修改内容':'首次实际原版内核同输入基线',
          '文档概述':'十一既有开发输入；无维护模块；保留全部返回面与真实失败',
          '索引目录':['rows'], 'status':'running', 'source_manifest_sha256':sha(manifest_path),
          'adapter_sha256':sha(here/'03-原生布尔质量与阶段计时.cpp'), 'remote':root, 'rows':[]}


def save():
    """每个事件结束即保存，未结束状态不提前计成功。"""
    (output/'01-原版生成阶段基线记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')


def execute(client, argv, log):
    """参数逐个引用，保留内核的完整原始日志与实际退出码。"""
    _, stream, _ = client.exec_command(shlex.join(argv))
    stream.channel.set_combine_stderr(True)
    text = stream.read().decode('utf8','replace')
    rc = stream.channel.recv_exit_status()
    log.write_text(text,'utf8')
    return rc,text


def quality(path):
    """独立用叉积与点积计算最小角、绝对坏面面积及拓扑，不清理输入。"""
    mesh = trimesh.load(path,process=False,force='mesh')
    t = np.asarray(mesh.vertices)[np.asarray(mesh.faces)]
    area = np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)/2
    angles = []
    for i in range(3):
        a,b = t[:,(i+1)%3]-t[:,i],t[:,(i+2)%3]-t[:,i]
        angles.append(np.degrees(np.arctan2(np.linalg.norm(np.cross(a,b),axis=1),np.einsum('ij,ij->i',a,b))))
    minimum = np.min(angles,axis=0)
    valid = np.isfinite(t).all(axis=(1,2)) & np.isfinite(area) & (area>0)
    return {'faces':len(t), 'nonpositive_or_nonfinite_faces':int((~valid).sum()),
            'below_10_faces':int(((minimum<10)&valid).sum()),
            'below_10_area_mm2':float(area[(minimum<10)&valid].sum()),
            'below_10_fraction':float(((minimum<10)&valid).sum()/len(t)),
            'watertight':bool(mesh.is_watertight),'winding_consistent':bool(mesh.is_winding_consistent),
            'euler_number':int(mesh.euler_number),'volume_mm3':float(mesh.volume)}


save()
client = remote.connect()
try:
    rc,_ = execute(client,['mkdir',root],output/'02-远端隔离目录创建日志.txt')
    assert rc==0
    with client.open_sftp() as sftp:
        sftp.put(str(here/'03-原生布尔质量与阶段计时.cpp'),root+'/driver.cpp')
        rc,_ = execute(client,['g++','-O3','-std=c++17',root+'/driver.cpp','-I'+source+'/src/lib',
                              '-L'+lib,'-Wl,-rpath,'+lib,'-lgeogram','-o',root+'/baseline'],output/'03-原版适配器编译日志.txt')
        assert rc==0
        rc,text=execute(client,['sha256sum',root+'/baseline',lib+'/libgeogram.so'],output/'04-原版执行文件摘要.txt')
        assert rc==0
        record['binary_and_library_hashes']=text
        for index,case in enumerate(manifest['cases']):
            folder=output/f'{index:02d}-{case["id"]}'
            folder.mkdir()
            for key in ('parent','tool'):
                assert sha(case[key])==case[key+'_sha256']
                sftp.put(case[key],root+'/'+key+'.obj')
            for mode in ('default','no_simplify'):
                args=[root+'/baseline',root+'/parent.obj',root+'/tool.obj',root+'/output.obj']
                if mode=='no_simplify': args.append('--no-simplify')
                rc,text=execute(client,args,folder/f'{mode}.log')
                row={'case':case['id'],'mode':mode,'returncode':rc,
                     'parent_sha256':case['parent_sha256'],'tool_sha256':case['tool_sha256']}
                if rc==0:
                    path=folder/f'{mode}.obj'
                    sftp.get(root+'/output.obj',str(path))
                    row['native_timing']=json.loads(next(line[len('NATIVE_RESULT '):] for line in text.splitlines() if line.startswith('NATIVE_RESULT ')))
                    row['quality']=quality(path)
                    row['output_path']=str(path)
                    row['output_sha256']=sha(path)
                record['rows'].append(row)
                save()
                print(case['id'],mode,rc,row.get('quality',{}).get('below_10_faces'),row.get('native_timing',{}).get('boolean_ms'),flush=True)
    record.update(status='completed_all_twenty_two_original_native_generations',finished_beijing=now())
    save()
finally:
    client.close()
