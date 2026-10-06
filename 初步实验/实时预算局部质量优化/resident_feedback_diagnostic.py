"""真实工具前缀的常驻父反馈诊断；保存全量对象供事后精确嵌入核查。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh
from benchmark import save_obj,quality
from geogram_memory import GeogramMemory
from maintain_input import maintain_input
from covered_zero_cleanup import clean_arrays
from numeric_input import check_and_boxes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--ct-record',type=Path,required=True)
    parser.add_argument('--positive-area-input',action='store_true')
    parser.add_argument('--covered-zero-cleanup',action='store_true')
    parser.add_argument('--no-simplify',action='store_true')
    args=parser.parse_args();args.root.mkdir(parents=True,exist_ok=False)
    source=json.loads(args.ct_record.read_text(encoding='utf-8'));events=source['routes'][0]['events']
    assert len(events)==16 and source['routes'][0]['complete']
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    initial_path=Path(events[0]['parent_path']);assert sha(initial_path)==events[0]['parent_sha256']
    initial=trimesh.load(initial_path,process=False);tools=[]
    for event in events:
        path=Path(event['tool_path']);assert sha(path)==event['tool_sha256']
        mesh=trimesh.load(path,process=False)
        tools.append((np.asarray(mesh.vertices),np.asarray(mesh.faces)))
    api=GeogramMemory();routes=[]
    report={'time_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'status':'running',
            'input_record':str(args.ct_record),'input_record_sha256':sha(args.ct_record),
            'initial':str(initial_path),'initial_sha256':sha(initial_path),
            'tool_sha256':[e['tool_sha256'] for e in events],
            'method_sources':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},
            'backend':'cpu','guard':'Python精确整数全域守卫','routes':routes,
            'certification':'诊断链事后核查，不计发布；任何无效源之后的结果均不能证明维护算法有效',
            'excluded_from_cut_maintenance_timing':['初态和预加载工具文件读取','保存OBJ与记录','全量前后质量统计','全量精确嵌入事后审计','显示'],
            'no_full_pamo':True,'minimum_input_area_mm2':0.0 if args.positive_area_input else 1e-12,
            'covered_zero_cleanup':args.covered_zero_cleanup,'no_simplify':args.no_simplify}
    def save():
        path=args.root/'01-实际常驻切削与预算维护父链诊断.json'
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
    save()
    for budget in (0,20,50,100,200):
        v=np.array(initial.vertices);f=np.array(initial.faces);parent_sha=sha(initial_path)
        route={'budget_ms':budget,'planned_events':16,'events':[],'status':'running'};routes.append(route);save()
        out=args.root/f'budget{budget}';out.mkdir();blocked=False
        for index,(tv,tf) in enumerate(tools):
            if blocked:
                route['events'].append({'step':index,'status':'blocked_by_previous_numeric_failure'});save();continue
            start=perf_counter();cv,cf,bits,timing=api.difference(v,f,tv,tf,no_simplify=args.no_simplify)
            cut_end=perf_counter()
            # 原始源有效性决定是否规范化，属于必要输入工作，必须计入预算。
            detector_start=perf_counter();invalid,_,_=check_and_boxes(cv,cf,report['minimum_input_area_mm2'])
            detector_ms=(perf_counter()-detector_start)*1000
            raw_quality=quality(cv,cf,report['minimum_input_area_mm2']);assert invalid==raw_quality['invalid']
            item={'step':index,'parent_sha256':parent_sha,'tool_sha256':events[index]['tool_sha256'],
                  'boolean':timing,'input_detector_ms':detector_ms,'raw_quality':raw_quality,'operand_bits_counts':dict(zip(*[x.tolist() for x in np.unique(bits,return_counts=True)])),
                  'status':'diagnostic_only_pending_embedding_audit'}
            raw=out/f'e{index:02d}_raw.obj';save_obj(raw,cv,cf);item.update(raw=str(raw),raw_sha256=sha(raw))
            # 即使数值拒绝也保存实际来源位，便于后续归因；历史失败目录不改写。
            item['raw_labels']=str(out/f'e{index:02d}_bits.npy');np.save(item['raw_labels'],bits)
            cleanup_ms=0.0
            if raw_quality['invalid'] and args.covered_zero_cleanup:
                clean_start=perf_counter()
                try:
                    cv,cf,bits,item['source_cleanup']=clean_arrays(cv,cf,bits)
                    cleanup_ms=(perf_counter()-clean_start)*1000
                    item['cleaned_quality']=quality(cv,cf,report['minimum_input_area_mm2'])
                    clean_path=out/f'e{index:02d}_cleaned.obj';save_obj(clean_path,cv,cf)
                    item.update(cleaned=str(clean_path),cleaned_sha256=sha(clean_path))
                    np.save(out/f'e{index:02d}_cleaned_bits.npy',bits)
                except ValueError as exc:item['source_cleanup_error']=str(exc)
            if item.get('cleaned_quality',raw_quality)['invalid']:
                item['status']='raw_numeric_invalid';blocked=True
            else:
                maintenance_start=perf_counter()
                if budget:
                    state,maintenance=maintain_input(cv,cf,bits,tv.min(0)-0.1,tv.max(0)+0.1,max(0,budget-detector_ms-cleanup_ms),minimum_input_area_mm2=report['minimum_input_area_mm2'])
                    nv,nf=state.vertices,state.faces;item['maintenance']=maintenance
                else:nv,nf=cv,cf
                maintenance_end=perf_counter()
                # 切削与维护只相加实际执行区间；穿插的诊断统计和保存耗时另计，不能当在线延迟。
                item['source_cleanup_plus_maintenance_ms']=detector_ms+cleanup_ms+(maintenance_end-maintenance_start)*1000
                item['source_and_maintenance_budget_overrun']=bool(budget and item['source_cleanup_plus_maintenance_ms']>budget)
                item['cut_plus_maintenance_ms']=(cut_end-start)*1000+item['source_cleanup_plus_maintenance_ms']
                item['after_quality']=quality(nv,nf,report['minimum_input_area_mm2'])
                item['vertices_unchanged_by_maintenance']=bool(np.array_equal(cv,nv))
                output=out/f'e{index:02d}_output.obj';save_obj(output,nv,nf)
                item.update(output=str(output),output_sha256=sha(output))
                v,f=np.array(nv),np.array(nf);parent_sha=item['output_sha256']
            item['diagnostic_wall_ms']=(perf_counter()-start)*1000
            route['events'].append(item);save()
            print(budget,index,item['status'],len(cf),raw_quality['invalid'],item.get('cut_plus_maintenance_ms'),flush=True)
        route['status']='numeric_blocked' if blocked else 'complete_diagnostic_pending_embedding_audit';save()
    report['status']='terminal_diagnostic_pending_embedding_audit';save()


if __name__=='__main__':main()
