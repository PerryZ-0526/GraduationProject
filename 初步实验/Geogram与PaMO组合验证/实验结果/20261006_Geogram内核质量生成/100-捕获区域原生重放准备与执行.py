"""用实际捕获数组进行小规模原生机理实验，所有参数和失败均保存。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import itertools
import json
import shlex
import numpy as np

here=Path(__file__).resolve().parent
folder=here/'捕获区域有界细化原生重放';folder.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
captured=here/'实际Triangle输入与非法队列捕获'
records=json.loads((captured/'01-actual_capture_record.json').read_text('utf8'))
paths=[]
for i in [5,6,10]:
    item=next(x for x in records['rows'] if x['case_index']==i)
    if i==10:
        lines=(captured/'10/actual.log').read_text('utf8').splitlines()
        done={json.loads(x[len('NATIVE_QUALITY_REGION '):])['group'] for x in lines if x.startswith('NATIVE_QUALITY_REGION ')}
        selected=[p for p in (captured/'10/input_arrays').glob('*.json') if json.loads(p.read_text('utf8'))['group'] not in done]
        assert len(selected)==1
    else:selected=list((captured/f'{i:02d}'/'input_arrays').glob('*.json'));assert len(selected)==1
    p=selected[0];assert sha(p)==item['captured_inputs'][p.name]
    d=json.loads(p.read_text('utf8'));xy=np.asarray(d['xy']).reshape(-1,2);xyz=np.asarray(d['xyz'])
    u,v=min(itertools.permutations(range(3),2),key=lambda uv:np.max(np.abs(xy-xyz[:,uv])))
    error=float(np.max(np.abs(xy-xyz[:,[u,v]])))
    assert error<1e-10
    data=folder/f'{i:02d}-实际区域重放输入.txt'
    data.write_text(f"{len(xy)} {len(d['cells'])//3} {len(d['segments'])//2} {u} {v}\n"+
                    ' '.join(format(x,'.17g') for x in d['xy'])+'\n'+
                    ' '.join(format(x,'.17g') for x in xyz.reshape(-1))+'\n'+
                    ' '.join(map(str,d['cells']))+'\n'+' '.join(map(str,d['segments']))+'\n','utf8')
    paths.append({'case_index':i,'source_sha256':sha(p),'group':d['group'],'input':str(data),'input_sha256':sha(data),
                  'projection_axes':[int(u),int(v)],'projection_match_error':error})
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
root='/tmp/geogram_native_quality_20261006_07';remote_folder=root+'/region_replay'
record={'生成时间':now(),'修改时间及修改内容':'实际捕获区域重放、定向面积细化及归一化诊断',
        '文档概述':'小规模区域机理实验，非完整布尔改善或速度结论','索引目录':['rows'],
        'status':'running','inputs':paths,'driver_sha256':sha(here/'99-捕获区域有界面积细化原生重放.cpp'),'rows':[]}
path=folder/'01-原生捕获区域细化实验记录.json'
def save():
    """实际每次原生返回码和日志完整记录。"""
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save();client=remote.connect()
try:
    _,out,_=client.exec_command('mkdir '+remote_folder);assert out.channel.recv_exit_status()==0
    with client.open_sftp() as sftp:
        sftp.put(str(here/'99-捕获区域有界面积细化原生重放.cpp'),remote_folder+'/replay.cpp')
        for item in paths:sftp.put(item['input'],remote_folder+f"/{item['case_index']:02d}.txt")
    argv=['g++','-O3','-std=c++17',remote_folder+'/replay.cpp','-I'+root+'/candidate_source/src/lib',
          '-L'+root+'/candidate_build/lib','-Wl,-rpath,'+root+'/candidate_build/lib','-lgeogram','-o',remote_folder+'/replay']
    _,out,_=client.exec_command(shlex.join(argv));out.channel.set_combine_stderr(True)
    text=out.read().decode('utf8','replace');rc=out.channel.recv_exit_status()
    (folder/'02-实际区域重放编译日志.txt').write_text(text,'utf8');record['compile_returncode']=rc;save();assert rc==0
    experiments=[(i,budget,boundary,normalization) for i in [5,6] for budget in [64,128,256]
                 for boundary in [False,True] for normalization in ['raw']]
    experiments += [(10,64,True,s) for s in ['raw','normalize']]
    for i,budget,boundary,normalization in experiments:
        options='rpzq20'+('' if boundary else 'YY')+f'S{budget}Q'
        tag=f'{i:02d}_{budget}_{int(boundary)}_{normalization}'
        _,out,_=client.exec_command(shlex.join([remote_folder+'/replay',remote_folder+f'/{i:02d}.txt',options,str(budget),normalization]))
        out.channel.set_combine_stderr(True);text=out.read().decode('utf8','replace');rc=out.channel.recv_exit_status()
        log=folder/(tag+'.log');log.write_text(text,'utf8')
        stages=[json.loads(line[len('REPLAY_STAGE '):]) for line in text.splitlines() if line.startswith('REPLAY_STAGE ')]
        record['rows'].append({'case_index':i,'total_point_budget':budget,'boundary_split':boundary,'normalization':normalization,
            'options':options,'returncode':rc,'log_sha256':sha(log),'stages':stages,
            'queue_failure_lines':[line for line in text.splitlines() if line.startswith('TRIANGLE_QUEUE_')]})
        save();print(tag,rc,[(s['stage'],s['bad'],s['bad_area'],s['points']) for s in stages],flush=True)
    record.update(status='completed_fourteen_actual_region_replay_experiments',finished_beijing=now());save()
except BaseException as error:
    record.update(status='failed_actual_region_replay_controller',error=str(error),finished_beijing=now());save();raise
finally:
    client.close()
