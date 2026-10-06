"""真实切削父反馈：必要源修复与精确证书计入预算，失败后保留完整计划分母。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh
from benchmark import quality,save_obj
from geogram_memory import GeogramMemory
from exact_mesh_memory import ExactMeshMemory
from incremental_mesh_memory import VerifiedMesh
from numeric_input import check_and_boxes
from covered_zero_cleanup import clean_arrays
from short_edge_repair import repair_short_edges
from native_guard import NativeLocalGuard,separated_native,load_library
from maintain_input import maintain_input


def main(publisher=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ct-record',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--budgets',type=float,nargs='+',default=[20,50,100,200])
    p.add_argument('--fixed-flip-certificate',action='store_true')
    p.add_argument('--early-quality-return',action='store_true')
    p.add_argument('--edge-backend',choices=['cpu','cuda'],default='cpu');args=p.parse_args()
    if args.early_quality_return and not args.fixed_flip_certificate:p.error('快速质量策略需要原生局部翻边证书')
    args.output.mkdir(parents=True,exist_ok=False)
    sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    # Linux独立编译链逐一绑定实际库字节；本机历史入口没有该记录时保持原行为。
    identity_path=Path(__file__).with_name('build_identity.json');build_identity=None
    if identity_path.exists():
        build_identity=json.loads(identity_path.read_text(encoding='utf-8'));assert build_identity['status']=='completed'
        for library in build_identity['libraries']:assert sha(library['path'])==library['sha256']
    source=json.loads(args.ct_record.read_text(encoding='utf-8'));events=source['routes'][0]['events']
    assert len(events)==16 and source['routes'][0]['complete']
    initial_path=Path(events[0]['parent_path']);assert sha(initial_path)==events[0]['parent_sha256']
    initial=trimesh.load(initial_path,process=False);iv,iff=np.asarray(initial.vertices),np.asarray(initial.faces)
    tools=[];full=ExactMeshMemory();startup=[]
    for e in events:
        path=Path(e['tool_path']);assert sha(path)==e['tool_sha256']
        m=trimesh.load(path,process=False);tv,tf=np.asarray(m.vertices),np.asarray(m.faces)
        check=full.audit(tv,tf);assert check['embedded_closed'];tools.append((tv,tf));startup.append(check)
    # GPU上下文先作为启动费用记录；每刀的实际索引上传、排序和下载仍由维护计时覆盖。
    gpu_startup=None
    if args.edge_backend=='cuda':
        gpu_start=perf_counter();import torch
        torch.cuda.init();torch.cuda.synchronize()
        gpu_startup=dict(device=torch.cuda.get_device_name(0),torch_version=torch.__version__,context_ms=(perf_counter()-gpu_start)*1000)
    api=GeogramMemory();load_library();routes=[]
    method_names=['verified_budget_feedback.py','incremental_mesh_memory.py','incremental_mesh_memory.cpp','exact_mesh_memory.cpp',
        'short_edge_repair.py','maintain_input.py','targeted_budget_flip.py','native_guard.py','numeric_input.py','covered_zero_cleanup.py',
        'gpu_edge_index.py','geogram_memory.py','geogram_memory.cpp','exact_mesh_memory.py','budget_flip.py','sparse_budget_flip.py','resumable_budget_flip.py','local_guard.py']
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',routes=routes,
        initial_sha256=sha(initial_path),tool_sha256=[e['tool_sha256'] for e in events],startup_tools= startup,
        method_sha256={n:sha(Path(__file__).with_name(n)) for n in method_names},no_full_pamo=True,
        parent_policy='仅精确证书成立的当前帧可反馈；超预算单列，不伪称硬实时通过',
        excluded_from_online_time=['初态与工具预加载和一次性认证','离线全量质量分布','保存文件和记录','显示'],
        comparison_scope='已见真实CT16工具同前缀，每档沿自己的当前合法父网格切削，不作未见患者保证')
    report['live_array_publication']=publisher is not None
    report['fixed_flip_certificate']=args.fixed_flip_certificate
    report['early_quality_return']=args.early_quality_return
    report['optional_quality_cap_ms']=30 if args.early_quality_return else None
    report['edge_backend']=args.edge_backend;report['gpu_startup']=gpu_startup
    report['build_identity']=build_identity
    def save():
        out=args.output/'01-真实父反馈四预算完整记录.json';temp=out.with_suffix('.tmp')
        temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(out)
    save()
    for budget in args.budgets:
        v,f=iv.copy(),iff.copy();certificate=VerifiedMesh();root_check=certificate.check(v,f,advance=True);assert root_check['embedded_closed']
        route=dict(budget_ms=budget,root_check=root_check,planned_events=16,events=[],status='running');routes.append(route)
        directory=args.output/f'budget{budget:g}';directory.mkdir();parent_sha=sha(initial_path);blocked=False
        for index,(tv,tf) in enumerate(tools):
            if blocked:
                route['events'].append(dict(step=index,status='blocked_by_previous_invalid_source'));save();continue
            item=dict(step=index,parent_sha256=parent_sha,tool_sha256=events[index]['tool_sha256'])
            whole_start=perf_counter();cv,cf,bits,boolean=api.difference(v,f,tv,tf,no_simplify=True)
            raw_v,raw_f,raw_bits=cv,cf,bits
            cut_end=perf_counter();maintenance_start=cut_end
            item['boolean']=boolean;cleanup=None;repair=None;maintenance=None;final_check=None;source_check=None
            source_v,source_f,source_bits=cv,cf,bits
            try:
                invalid,_,_=check_and_boxes(cv,cf,0)
                if invalid:
                    cv,cf,bits,cleanup=clean_arrays(cv,cf,bits)
                    invalid,_,_=check_and_boxes(cv,cf,0)
                    # 三点不同的共线面不直接删除；允许后续受约束短边替换尝试恢复合法源。
                remaining=budget-(perf_counter()-maintenance_start)*1000
                # 必需极短边处理先执行；为精确源核查预留实测原子工作时间，越界仍如实报告。
                cv,cf,bits,repair=repair_short_edges(cv,cf,bits,v,max(0,remaining-50),separation_check=separated_native)
                source_v,source_f,source_bits=cv,cf,bits
                invalid,_,_=check_and_boxes(cv,cf,0)
                if invalid:raise ValueError('完整源修复后仍含非正面积或非有限源')
                source_check=certificate.check(cv,cf,advance=True)
                if not source_check['embedded_closed']:raise ValueError('切削源修复后仍未通过精确闭合嵌入核查')
                remaining=budget-(perf_counter()-maintenance_start)*1000
                if remaining>(45 if args.early_quality_return else 70):
                    # 源已认证才进入质量操作；保留再次认证及输出复制时间，失败则返回合法源。
                    # 先交付策略限制整个质量准备与操作阶段30ms、最多4次，不用完200ms额度。
                    quality_budget=min(30,remaining-15) if args.early_quality_return else remaining-50
                    state,maintenance=maintain_input(cv,cf,bits,tv.min(0),tv.max(0),quality_budget,
                        guard_class=NativeLocalGuard,minimum_input_area_mm2=0,max_flips=4 if args.early_quality_return else 16,edge_backend=args.edge_backend)
                    if maintenance['accepted']:
                        # 新机制原生重验实际翻边记录、拓扑和全域障碍；历史重建路径明确保留作对照。
                        final_check=(certificate.check_flips(state.vertices,state.faces,maintenance['operations']) if args.fixed_flip_certificate
                                     else certificate.check(state.vertices,state.faces,advance=True))
                        if final_check['embedded_closed']:cv,cf,bits=state.vertices,state.faces,state.bits
                # 发布数组独立拥有内存；这项复制和必要元数据组织也在维护计时内。
                v,f,bits=cv.copy(),cf.copy(),bits.copy()
                item.update(status='published_verified',source_check=source_check,final_check=final_check,
                    cleanup=cleanup,repair=repair,maintenance=maintenance)
            except Exception as error:
                item.update(status='source_rejected',error=repr(error),cleanup=cleanup,repair=repair,maintenance=maintenance)
                if source_check is not None:item['source_check']=source_check
                source_v,source_f,source_bits=cv,cf,bits
                blocked=True
            item['maintenance_total_ms']=(perf_counter()-maintenance_start)*1000
            item['cut_and_maintenance_ms']=(perf_counter()-whole_start)*1000
            item['budget_overrun']=item['maintenance_total_ms']>budget
            if publisher is not None:
                # 在线接口直接发送新计算的数组，不等待OBJ保存与全量质量统计。
                if not blocked:
                    h=hashlib.sha256()
                    for array in (v,f,bits):h.update(memoryview(np.ascontiguousarray(array)).cast('B'))
                    item['output_array_sha256']=h.hexdigest()
                    item['tool_arrival_perf_counter']=whole_start
                    item['maintenance_total_ms']=(perf_counter()-maintenance_start)*1000
                    item['cut_and_maintenance_ms']=(perf_counter()-whole_start)*1000
                    item['budget_overrun']=item['maintenance_total_ms']>budget
                    publisher(v,f,bits,tv,tf,dict(item))
                    parent_sha=item['output_array_sha256']
                route['events'].append(item);save();continue
            # 离线保存与质量分布不会倒填到在线计时，但所有正面积小面仍在质量分母中。
            raw_path=directory/f'e{index:02d}_raw.obj';save_obj(raw_path,raw_v,raw_f)
            item.update(raw_path=str(raw_path),raw_sha256=sha(raw_path),raw_quality=quality(raw_v,raw_f,0))
            np.save(directory/f'e{index:02d}_raw_bits.npy',raw_bits)
            source_path=directory/f'e{index:02d}_source.obj';save_obj(source_path,source_v,source_f)
            item.update(source_path=str(source_path),source_sha256=sha(source_path))
            np.save(directory/f'e{index:02d}_source_bits.npy',source_bits)
            item['source_quality']=quality(source_v,source_f,0)
            if not blocked:
                out=directory/f'e{index:02d}_output.obj';save_obj(out,v,f)
                item.update(output_path=str(out),output_sha256=sha(out),output_quality=quality(v,f,0))
                parent_sha=item['output_sha256'];print(json.dumps(dict(budget=budget,step=index,status=item['status'],ms=item['maintenance_total_ms'],over=item['budget_overrun'],flips=maintenance['accepted'] if maintenance else 0)),flush=True)
            else:print(json.dumps(dict(budget=budget,step=index,status=item['status'],error=item['error'])),flush=True)
            route['events'].append(item);save()
        certificate.close();route['status']='completed';route['valid_published']=sum(e['status']=='published_verified' for e in route['events']);save()
    report['status']='completed';save()


if __name__=='__main__':main()
