"""同物理轨迹的六种维护调度真实父反馈，计入检查和传输开销。"""
import argparse
from collections import Counter
import getpass
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
from time import perf_counter
import numpy as np
import paramiko
import trimesh
from cadence_policy import POLICIES,ADAPTIVE,maintenance_reason
from audit_followup_candidate import sha256,quality_distribution
from locality_cleanup import clean_provenance
from locality_masks import save_obj_fp64
from preserved_feedback_gate import check_preserved_mesh
from run_constrained_feedback import global_geometry,PROVENANCE
from run_geometry_study import execute,retrieve,save,now,PYTHON,GEO,REMOTE_BASE,EXPECTED_EXTENSION
from audit_cut_embedding import CHECKER
from freeze_ordered_evaluation import runtime_sources,runtime_source_path

HERE=Path(__file__).resolve().parent


class Engine:
    def __init__(self,output,port):
        self.output=output
        self.remote=REMOTE_BASE+'/cadence_'+hashlib.sha256(str(output.resolve()).encode()).hexdigest()[:16]
        self.client=paramiko.SSHClient();self.client.load_system_host_keys()
        password=getpass.getpass('GPU SSH password: ')
        self.client.connect(os.environ.get('GPU_SSH_HOST','connect.westb.seetacloud.com'),port=port,
                            username='root',password=password,look_for_keys=False,allow_agent=False,timeout=30)
        del password
        self.client.get_transport().set_keepalive(30);self.sftp=self.client.open_sftp()

    def setup(self):
        if execute(self.client,['mkdir',self.remote])['returncode']:raise ValueError('远端批次已存在，不覆盖')
        for name in ('cadence_pamo_worker.py','locality_masks.py'):
            self.sftp.put(str(HERE/name),self.remote+'/'+name)
        result=execute(self.client,['env','LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6',PYTHON,'-c',
            "import torch,pamo,torchcumesh2sdf,json,hashlib; print(json.dumps({'device':torch.cuda.get_device_name(0),'torch':torch.__version__,'pamo_sha256':hashlib.sha256(open(pamo.__file__,'rb').read()).hexdigest(),'extension_sha256':hashlib.sha256(open(torchcumesh2sdf.__file__,'rb').read()).hexdigest()}))"])
        if result['returncode']:raise RuntimeError(result['stderr'])
        info=json.loads(result['stdout'].strip().splitlines()[-1])
        if info['extension_sha256']!=EXPECTED_EXTENSION:raise ValueError('作者符号扩展版本改变')
        info['checker_sha256']=execute(self.client,['sha256sum',CHECKER])['stdout'].split()[0]
        if info['checker_sha256']!='0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3':raise ValueError('精确检查器改变')
        info['geogram_sha256']=execute(self.client,['sha256sum',GEO])['stdout'].split()[0]
        self.info=info
        return info

    def difference(self,parent,tool,folder,stem):
        remote=self.remote+'/'+stem
        self.sftp.put(str(parent),remote+'_parent.obj');self.sftp.put(str(tool),remote+'_tool.obj')
        run=execute(self.client,[PROVENANCE,remote+'_parent.obj',remote+'_tool.obj',remote+'_raw.obj',remote+'_labels.json','--no-simplify'],remote+'_geogram.log',timeout=120)
        retrieve(self.client,self.sftp,remote+'_geogram.log',folder/'geogram.log')
        if run['returncode']:return None,run
        for suffix,name in (('_raw.obj','raw.obj'),('_labels.json','labels.json')):
            retrieve(self.client,self.sftp,remote+suffix,folder/name)
        raw=trimesh.load(folder/'raw.obj',process=False)
        labels=json.loads((folder/'labels.json').read_text(encoding='utf-8'))['operand_bits']
        # 所有策略共用同一个表示清理；没有按策略或输入编号增加修复。
        mesh,bits,cleanup=clean_provenance(raw,labels,allow_shared=True)
        save_obj_fp64(mesh,folder/'source.obj')
        run['common_cleanup']=cleanup
        return mesh,run

    def pamo(self,source,folder,stem):
        remote=self.remote+'/'+stem
        self.sftp.put(str(source),remote+'_source.obj')
        run=execute(self.client,['env','LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6','PYTHONPATH='+self.remote,
            PYTHON,self.remote+'/cadence_pamo_worker.py','--source',remote+'_source.obj','--output',remote+'_pamo'],remote+'_pamo.log',timeout=600)
        retrieve(self.client,self.sftp,remote+'_pamo.log',folder/'pamo.log')
        if run['returncode']:return None,run
        for name in ('candidate.obj','details.json'):
            retrieve(self.client,self.sftp,remote+'_pamo/'+name,folder/name)
        details=json.loads((folder/'details.json').read_text(encoding='utf-8'))
        if details['extension_sha256']!=EXPECTED_EXTENSION or details['installed_pamo_sha256']!=self.info['pamo_sha256']:
            raise ValueError('实际PaMO进程版本与批次不符')
        if details['source_sha256']!=sha256(source):raise ValueError('实际PaMO输入不符')
        run['details']=details
        return trimesh.load(folder/'candidate.obj',process=False),run

    def close(self):
        self.sftp.close();self.client.close()


def prepare_references(engine,args,route,index):
    initial=args.prepared/'inputs'/route['initial_mesh']
    folder=args.output/f'reference_{index}';folder.mkdir()
    initial_mesh=trimesh.load(initial,process=False)
    initial_ok,metrics=check_preserved_mesh(engine,folder,initial_mesh,'initial')
    result=dict(initial_valid=initial_ok,initial_metrics=metrics,rows=[])
    refs={};union=None
    for step,item in enumerate(route['prefix_tools']):
        current=folder/f'step_{step}';current.mkdir()
        tool=args.prepared/'inputs'/item['mesh']
        remote_tool=engine.remote+f'/reference_{index}_{step}_tool.obj'
        engine.sftp.put(str(tool),remote_tool)
        if union is None:
            union=remote_tool
        else:
            target=engine.remote+f'/reference_{index}_{step}_union.obj'
            run=execute(engine.client,[GEO,union,remote_tool,target,'--operation','union','--no-simplify'],target+'.log')
            retrieve(engine.client,engine.sftp,target+'.log',current/'union.log')
            if run['returncode']:
                result['rows'].append(dict(event=item['event_id'],status='reference_union_failed',run=run));break
            union=target
        union_local=current/'union.obj';retrieve(engine.client,engine.sftp,union,union_local)
        try:mesh,run=engine.difference(initial,union_local,current,f'reference_{index}_{step}_difference')
        except ValueError as error:
            result['rows'].append(dict(event=item['event_id'],status='reference_cleanup_rejected',error=str(error)));continue
        if mesh is None:
            result['rows'].append(dict(event=item['event_id'],status='reference_execution_failed',run=run));continue
        valid,checks=check_preserved_mesh(engine,current,mesh,'reference')
        result['rows'].append(dict(event=item['event_id'],status='reference_valid' if valid else 'reference_invalid',source_sha256=sha256(current/'source.obj'),metrics=checks))
        if valid:refs[item['event_id']]=(mesh,checks,current/'source.obj')
    save(folder/'01-独立累计工具参照.json',result)
    return initial_ok,refs


def step(engine,args,route,item,parent,state,policy,folder,stem,final,reference):
    start=perf_counter()
    tool=args.prepared/'inputs'/item['mesh']
    row=dict(route=route['id'],event=item['event_id'],policy=policy,parent_sha256=sha256(parent),tool_sha256=sha256(tool),maintenance_calls=0)
    def finish(status,parent_path=None):
        # 拒绝帧同样计入真实执行成本，不能只统计成功帧。
        row.update(status=status,frame_wall_ms=(perf_counter()-start)*1000,time_beijing=now())
        return row,parent_path
    # 各帧重新核查同次源对象；跳过时只复用同一帧同一字节的证据。
    engine.preserved_embedding_cache={}
    try:mesh,run=engine.difference(parent,tool,folder,stem)
    except ValueError as error:
        row['error']=str(error)
        return finish('common_cleanup_rejected')
    row['geogram']=run
    if mesh is None:return finish('geogram_failed')
    row['source_sha256']=sha256(folder/'source.obj')
    valid,source_metrics=check_preserved_mesh(engine,folder/'checks',mesh,'source')
    row['source_metrics']=source_metrics
    if not source_metrics['finite']:return finish('nonfinite_source_rejected')
    decision_start=perf_counter();current=quality_distribution(mesh)
    state['pending']+=1
    reason=maintenance_reason(policy,state['pending'],current,state['baseline'],final=final,valid=valid)
    row.update(source_quality=current,maintenance_reason=reason,pending_before_maintenance=state['pending'],decision_ms=(perf_counter()-decision_start)*1000)
    row['gpu_processes_before']=execute(engine.client,['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader'])['stdout'].strip()
    if reason:
        row['maintenance_calls']=1
        candidate,pamo=engine.pamo(folder/'source.obj',folder,stem)
        row['pamo']=pamo
        if candidate is None:return finish('maintenance_execution_failed')
    else:
        candidate=mesh
        shutil.copyfile(folder/'source.obj',folder/'candidate.obj')
    row['candidate_sha256']=sha256(folder/'candidate.obj')
    good,checks=check_preserved_mesh(engine,folder/'checks',candidate,'candidate')
    ref,ref_checks,_=reference
    geometry=global_geometry(candidate,ref)
    row.update(output_metrics=checks,output_quality=quality_distribution(candidate),cumulative_geometry=geometry)
    topology=(checks['components'],checks['euler_number'])==(ref_checks['components'],ref_checks['euler_number'])
    accepted=good and topology and geometry['probe_max_mm']<=0.1
    row.update(expected_topology_matches=topology)
    if accepted and reason:
        state.update(pending=0,baseline=row['output_quality'])
    return finish('published' if accepted else 'candidate_audit_rejected',folder/'candidate.obj' if accepted else None)


def run(args):
    manifest_path=args.prepared/'01-完整范围冻结清单.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    routes=[r for r in manifest['routes'] if r['split']==args.split]
    for route in routes:
        for name,digest in [(route['initial_mesh'],route['initial_mesh_sha256']),*[(t['mesh'],t['sha256']) for t in route['prefix_tools']]]:
            if sha256(args.prepared/'inputs'/name)!=digest:raise ValueError('冻结输入改变')
    report=dict(time_beijing=now(),status='running',manifest_sha256=sha256(manifest_path),planned_routes=len(routes),
                planned_events=sum(len(r['prefix_tools']) for r in routes)*len(POLICIES)*args.rounds,policies=POLICIES,rounds=args.rounds,routes=[])
    engine=Engine(args.output,args.port)
    try:
        report['environment']=engine.setup();save(args.output/'03-批次环境与完整分母.json',report)
        with (args.output/'04-逐刀真实父反馈记录.jsonl').open('x',encoding='utf-8') as ledger:
            for index,route in enumerate(routes):
                initial_ok,references=prepare_references(engine,args,route,index)
                initial=args.prepared/'inputs'/route['initial_mesh']
                for repeat in range(args.rounds):
                    rng=random.Random(2026100607+index*100+repeat)
                    states={policy:dict(parent=initial,pending=0,baseline=quality_distribution(trimesh.load(initial,process=False)),blocked=not initial_ok,published=0,rows=[]) for policy in POLICIES}
                    for position,item in enumerate(route['prefix_tools']):
                        order=list(POLICIES);rng.shuffle(order)
                        for policy in order:
                            state=states[policy]
                            folder=args.output/f'route{index}_round{repeat}_{policy}_step{position}';folder.mkdir()
                            if state['blocked']:
                                row=dict(route=route['id'],event=item['event_id'],policy=policy,status='blocked_by_previous_failure',maintenance_calls=0)
                            elif item['event_id'] not in references:
                                row=dict(route=route['id'],event=item['event_id'],policy=policy,status='reference_unavailable',maintenance_calls=0)
                                state['blocked']=True
                            else:
                                row,new_parent=step(engine,args,route,item,state['parent'],state,policy,folder,folder.name,
                                                    position==len(route['prefix_tools'])-1,references[item['event_id']])
                                if new_parent is None:state['blocked']=True
                                else:state['parent']=new_parent;state['published']+=1
                            row.update(round=repeat,published_version=state['published'])
                            save(folder/'audit.json',row);state['rows'].append(row)
                            ledger.write(json.dumps(row,ensure_ascii=False)+'\n');ledger.flush()
                            print(index,repeat,item['event_id'],policy,row['status'],row.get('maintenance_reason'),flush=True)
                    for policy,state in states.items():
                        report['routes'].append(dict(route=route['id'],round=repeat,policy=policy,planned_events=len(route['prefix_tools']),
                            published=state['published'],maintenance_calls=sum(r['maintenance_calls'] for r in state['rows']),status_counts=dict(Counter(r['status'] for r in state['rows'])),
                            pipeline_wall_ms=sum(r.get('frame_wall_ms',0) for r in state['rows']),final_parent_sha256=sha256(state['parent'])))
                    save(args.output/'03-批次环境与完整分母.json',report)
        report.update(status='completed_with_recorded_outcomes',finished_beijing=now())
        save(args.output/'03-批次环境与完整分母.json',report)
    finally:engine.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('prepared','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--split',choices=('development','evaluation'),required=True)
    parser.add_argument('--rounds',type=int,required=True)
    parser.add_argument('--frozen',action='store_true')
    args=parser.parse_args()
    if args.rounds<1:parser.error('rounds必须至少为1')
    if args.frozen:
        frozen=json.loads((args.output/'01-方法与调度冻结.json').read_text(encoding='utf-8'))
        for row in frozen['files']:
            if sha256(HERE/row['file'])!=row['sha256']:raise ValueError('实际运行冻结源码改变')
        run(args)
    else:
        args.output.mkdir(exist_ok=False);runtime=args.output/'runtime';runtime.mkdir()
        names=runtime_sources(HERE,['run_cadence_feedback.py','cadence_pamo_worker.py'])
        for name in names:shutil.copyfile(runtime_source_path(HERE,name),runtime/name)
        save(args.output/'01-方法与调度冻结.json',dict(time_beijing=now(),files=[dict(file=n,sha256=sha256(runtime/n)) for n in names],
            policies=POLICIES,adaptive=ADAPTIVE,geometry_budget_mm=0.1,quality_policy='统计与触发，不作质量拒绝',ratio=1.0,full_stages=True,
            final_flush='除never外末帧所有未维护切削均整理，费用计入该帧',rounds=args.rounds,split=args.split,
            timing_scope='逐刀Geogram、清理、决策、进程、传输、有效性及质量和几何审计；独立离线参照构建排除，未包含真实跟踪和渲染'))
        result=subprocess.run([sys.executable,str(runtime/'run_cadence_feedback.py'),*sys.argv[1:],'--frozen'])
        raise SystemExit(result.returncode)
