"""在相同真实父输入上检查原版禁共面简化输出，定位零面积与差面生成阶段。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast
import hashlib
import importlib.util
import json
import shlex
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
root='/tmp/geogram_native_quality_20261006_02'
manifest=json.loads((here/'18-原生十一同输入开发与速度运行前清单.json').read_text('utf8'))
code=ast.parse((here/'04-原版生成阶段同输入基线.py').read_text('utf8'))
function=next(n for n in code.body if isinstance(n,ast.FunctionDef) and n.name=='quality')
scope={'np':np,'trimesh':trimesh};exec(compile(ast.Module(body=[function],type_ignores=[]),'quality_detector','exec'),scope)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
output=here/'真实CT原版禁简化阶段定位';output.mkdir()
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'首次CT相同输入禁共面简化来源定位','文档概述':'原始交线细分输出，不接质量维护；保存与精确检查均实际执行',
        '索引目录':['rows'],'status':'running','rows':[]}
client=remote.connect()
try:
    with client.open_sftp() as sftp:
        for i in [9,10]:
            case=manifest['cases'][i]
            args=[root+'/baseline',root+f'/inputs/{i:02d}_parent.obj',root+f'/inputs/{i:02d}_tool.obj',root+f'/ct_raw_{i}.obj','--no-simplify']
            _,out,_=client.exec_command(shlex.join(args));out.channel.set_combine_stderr(True)
            text=out.read().decode('utf8','replace');rc=out.channel.recv_exit_status()
            (output/f'{i:02d}-原始交线生成日志.txt').write_text(text,'utf8')
            row={'case':case['id'],'returncode':rc,'parent_sha256':case['parent_sha256'],'tool_sha256':case['tool_sha256']}
            if rc==0:
                path=output/f'{i:02d}-原始交线生成网格.obj'
                sftp.get(root+f'/ct_raw_{i}.obj',str(path))
                row.update(output_path=str(path),output_sha256=sha(path),quality=scope['quality'](path))
                diagnosis='/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis'
                _,out,err=client.exec_command(shlex.join([diagnosis,root+f'/ct_raw_{i}.obj']))
                stdout=out.read().decode('utf8','replace');stderr=err.read().decode('utf8','replace');rc=out.channel.recv_exit_status()
                row['native_audit']={'returncode':rc,'stdout':stdout,'stderr':stderr}
                print(case['id'],row['quality'],row['native_audit'],flush=True)
            record['rows'].append(row)
            (output/'01-真实CT禁简化来源阶段记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
    record.update(status='completed_two_saved_raw_CT_stage_diagnoses',finished_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'))
    (output/'01-真实CT禁简化来源阶段记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
finally:
    client.close()
