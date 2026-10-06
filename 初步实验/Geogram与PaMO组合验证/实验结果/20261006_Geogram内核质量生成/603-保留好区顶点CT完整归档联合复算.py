"""复核每刀实际父链、保存摘要和准确检查，报告完整拒绝分母与同源分布。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast
import hashlib
import json
import numpy as np
import trimesh
import pyvista as pv
import vtk
import zipfile
import io

here=Path(__file__).resolve().parent
folder=here/'保留好区顶点原生CT十六刀全部实际输出'
record_path=folder/'01-原生CT十六刀反馈实际记录.json'
archive=zipfile.ZipFile(here/'602-保留好区顶点原生CT十六刀完整归档.zip')
record=json.loads(archive.read(record_path.name))
base_trimesh=trimesh
class ArchivedMeshReader:
    """完整ZIP读取原始输出，不重复解包。"""
    def load(self,path,**kwargs):
        path=Path(path)
        if path.is_relative_to(folder):
            return base_trimesh.load(io.BytesIO(archive.read(path.relative_to(folder).as_posix())),file_type='obj',**kwargs)
        return base_trimesh.load(path,**kwargs)
trimesh=ArchivedMeshReader()
def bytes_of(path):
    """本机固定输入和归档输出都核查实际原字节。"""
    return archive.read(path.relative_to(folder).as_posix()) if path.is_relative_to(folder) else path.read_bytes()
def text_of(path):
    """日志及审计读取完整原归档。"""
    return bytes_of(path).decode('utf8')
manifest_path=here/'597-保留好区顶点原生CT十六刀冻结清单.json'
manifest=json.loads(manifest_path.read_text('utf8'))
sha=lambda p:hashlib.sha256(bytes_of(p)).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
assert record['status'] in ['completed_all_planned_events_with_rejections','completed_sixteen_native_candidate_feedback_events']
assert len(record['events'])==record['planned_events']==len(manifest['tools'])==16
assert record['manifest_sha256']==sha(manifest_path)
assert record['build_sha256']==manifest['candidate_build_sha256']==sha(here/'595-保留好区顶点免重建实际原生编译记录.json')
# 提取纯复算函数，避免导入执行远程任务的历史入口。
def load_functions(path,names):
    module=ast.parse(path.read_text('utf8'))
    nodes=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in names]
    scope={'np':np,'trimesh':trimesh,'pv':pv,'vtk':vtk}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return scope
quality=load_functions(here/'04-原版生成阶段同输入基线.py',{'quality'})['quality']
funcs=load_functions(here/'301-新边收缩十二输入全部重复质量几何速度复算.py',{'distances','timing'})
output=here/'604-保留好区顶点原生CT十六刀保存联合复算.json';assert not output.exists()
summary={'生成时间':now(),'修改时间及修改内容':'首次完整16事件保存父链及同父质量复算',
 '文档概述':'原生实际反馈；原版按同候选父输入对照；双向几何为有限抽样，不是独立累计参照或连续证书',
 '索引目录':['preflight','events','totals'],'status':'running','worker_status':record['status'],
 'source_record_sha256':sha(record_path),'preflight':[],'events':[]}
def save():
    """逐项真实复算后保存，任何未完成不称全通过。"""
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
def checked(info):
    """重读同保存对象准确审计，不从控制器退出码推断几何成功。"""
    path=folder/Path(info['path']).name;assert sha(path)==info['sha256']
    audit=json.loads(text_of(path));assert audit['mesh_sha256']==info['mesh_sha256']
    result=json.loads(audit['stdout']);assert audit['returncode']==0
    assert bool(result['embedded_closed'])==info['embedded_closed']
    return result
for row in record['preflight']:
    actual=checked(row['audit']);assert actual['embedded_closed']
    summary['preflight'].append({'object':row['object'],'audit':actual})
save();parent=here/'原生CT十六刀开发冻结输入'/manifest['initial']['file']
assert sha(parent)==manifest['initial']['sha256'];blocked=False
times={'baseline':[],'candidate':[]}
for i,event in enumerate(record['events']):
    assert event['event_index']==i and event['tool_sha256']==manifest['tools'][i]['sha256']
    row={'event_index':i,'status':event['status']}
    if blocked:
        assert event['status']=='blocked_by_preceding_rejection'
        summary['events'].append(row);save();continue
    assert event['parent_sha256']==sha(parent)
    row.update(parent_sha256=sha(parent),parent_quality=quality(parent),methods={})
    for method,data in event['methods'].items():
        log=folder/f'e{i:02d}_{method}.log';assert sha(log)==data['log_sha256']
        # 超时或执行失败仍属完整事件，保留失败日志且不能补造网格与内核耗时。
        if data['returncode']!=0:
            row['methods'][method]={'returncode':data['returncode'],'log_sha256':sha(log),
                'subprocess_wall_ms':data['subprocess_wall_ms'],'saved_native_output_available':False}
            continue
        mesh=folder/Path(data['mesh_path']).name;assert sha(mesh)==data['mesh_sha256']
        audit=checked(data['audit']);q=quality(mesh)
        assert q['faces']==data['native_timing']['faces']
        times[method].append(data['native_timing']['boolean_ms'])
        row['methods'][method]={'quality':q,'audit':audit,'native_timing':data['native_timing'],
            'machine_edge_log':[line for line in text_of(log).splitlines() if 'contracted_zero_length_edges=' in line]}
    b=folder/f'e{i:02d}_baseline.obj';c=folder/f'e{i:02d}_candidate.obj'
    if all('audit' in row['methods'][m] for m in ['baseline','candidate']):
        row['geometry_same_input_output_comparison']={'baseline_to_candidate':funcs['distances'](b,c,2026100710+i),
            'candidate_to_baseline':funcs['distances'](c,b,2026100740+i),
            'baseline_embedded_closed':row['methods']['baseline']['audit']['embedded_closed']}
        row['removed_volume_mm3']=row['parent_quality']['volume_mm3']-row['methods']['candidate']['quality']['volume_mm3']
    valid=bool(row['methods']['candidate'].get('audit',{}).get('embedded_closed',False))
    assert valid==(event['status']=='accepted_native_output')
    if valid:parent=c
    else:blocked=True
    summary['events'].append(row);save()
summary.update(status='completed_all_sixteen_events_saved_parent_chain_quality_geometry_recomputation',
 finished_beijing=now(),totals={'accepted':sum(e['status']=='accepted_native_output' for e in summary['events']),
 'rejected':sum(e['status']=='rejected_native_output' for e in summary['events']),
 'blocked':sum(e['status']=='blocked_by_preceding_rejection' for e in summary['events']),
 'planned':16,'timing_per_actual_event':{m:funcs['timing'](values) for m,values in times.items()}})
save();print(json.dumps(summary['totals'],ensure_ascii=False))
