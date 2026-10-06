"""复用冻结质量算法的数组入口；完整长轨迹与独立材料参照分别从初态执行。"""
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np


ROOT = Path(__file__).resolve().parent
WORKERS = ROOT / 'workers'
sys.path.insert(0, str(WORKERS))


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    temporary = Path(path).with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def adapt(no_quality):
    text = (WORKERS / 'verified_budget_feedback.py').read_text(encoding='utf-8')
    replacements = {
        "assert len(events)==16 and source['routes'][0]['complete']": "assert events and source['routes'][0]['complete']",
        "planned_events=16": "planned_events=len(events)",
        "comparison_scope='已见真实CT16工具同前缀，每档沿自己的当前合法父网格切削，不作未见患者保证'":
            "comparison_scope='冻结384步开发输入，从原初态反馈自身实际数组；不作任意输入或临床保证'",
        "                    publisher(v,f,bits,tv,tf,dict(item))":
            "                    # 只读暴露实际原始源与维护源，保存和复审在数组交付后执行。\n"
            "                    publisher.raw=(raw_v,raw_f,raw_bits)\n"
            "                    publisher.source=(source_v,source_f,source_bits)\n"
            "                    publisher(v,f,bits,tv,tf,dict(item))",
        "                route['events'].append(item);save();continue":
            "                # 拒绝对象同样保留，但不会被当作已发布数组。\n"
            "                if blocked:publisher.failure((raw_v,raw_f,raw_bits),(source_v,source_f,source_bits),dict(item))\n"
            "                route['events'].append(item);save();continue",
    }
    config=json.loads((ROOT/'run_config.json').read_text())
    if config['complete_short_repair']:
        # 每次收缩至少删两面；以面数给出自然上限，仍保持原时限和全部提交守卫。
        before='cv,cf,bits,v,max(0,remaining-50),separation_check=separated_native)'
        replacements[before]='cv,cf,bits,v,max(0,remaining-50),max_collapses=len(cf)//2,separation_check=separated_native)'
    if config.get('geogram_simplify'):
        # 参数对照启用作者已有共面简化，输出仍接受相同精确认证。
        replacements['no_simplify=True,certified_operands=args.certified_operand_pairs)']='no_simplify=False,certified_operands=args.certified_operand_pairs)'
    if config.get('cancel_opposed_after_repair'):
        before='                source_v,source_f,source_bits=cv,cf,bits\n                invalid,_,_=check_and_boxes(cv,cf,0)\n'
        replacements[before]='''                # 必要修复后严格抵消反向面，再执行原精确源认证。
                from resident_source_cleanup import cancel_opposed_index_faces
                cv,cf,bits,opposed=cancel_opposed_index_faces(cv,cf,bits)
                repair['opposed_exact_index_cancellation']=opposed
                source_v,source_f,source_bits=cv,cf,bits
                invalid,_,_=check_and_boxes(cv,cf,0)
'''
    if config.get('cluster_source_fallback'):
        # 非正面积源也允许进入同一受认证成组事务，不在提出修复前直接拒绝。
        before="                if invalid:raise ValueError('完整源修复后仍含非正面积或非有限源')\n                source_check=certificate.check(cv,cf,advance=True)"
        replacements[before]='''                # 非有限坐标仍拒绝；有限退化源先标记失败，交给下方同一成组事务与精确认证。
                if invalid and not np.isfinite(cv).all():raise ValueError('完整源修复后仍含非有限源')
                source_check=(dict(embedded_closed=False,advanced=False,numeric_invalid_source=True)
                              if invalid else certificate.check(cv,cf,advance=True))'''
        before="                if not source_check['embedded_closed']:raise ValueError('切削源修复后仍未通过精确闭合嵌入核查')"
        replacements[before]='''                # 原源认证失败且未推进父证书时，尝试整体极短边事务；认证成功才替换实际源。
                if not source_check['embedded_closed']:
                    from resident_source_cleanup import repair_short_edge_clusters
                    # 方法尺度来自本批冻结配置，不根据路线或事件编号调整。
                    config_path=Path(__file__).resolve().parent.parent/'run_config.json'
                    tolerance=json.loads(config_path.read_text())['cluster_tolerance_mm']
                    nv,nf,nb,cluster=repair_short_edge_clusters(cv,cf,bits,v,tolerance_mm=tolerance)
                    cluster['original_failed_check']=source_check
                    if cluster['candidate']:
                        candidate_check=certificate.check(nv,nf,advance=True)
                        cluster['candidate_check']=candidate_check
                        cluster['accepted']=candidate_check['embedded_closed']
                        if cluster['accepted']:
                            cv,cf,bits=nv,nf,nb
                            source_v,source_f,source_bits=cv,cf,bits
                            source_check=candidate_check
                    else:cluster['accepted']=False
                    repair['source_cluster_fallback']=cluster
                if not source_check['embedded_closed']:raise ValueError('切削源修复后仍未通过精确闭合嵌入核查')'''
    if no_quality:
        replacements["                if remaining>(45 if args.early_quality_return else 70):"] = \
            "                # 独立材料参照只做必要修复和认证，不进行可选质量翻边。\n                if False:"
    for before, after in replacements.items():
        if text.count(before) != 1:
            raise ValueError('冻结入口适配锚点不唯一：' + before)
        text = text.replace(before, after)
    # 每个事件只追加一次账本；终态才保存完整记录，避免重复写入全部历史。
    start = text.index('    def save():\n')
    end = text.index('    save()\n    for budget', start)
    text = text[:start] + """    saved_count=0
    def save():
        nonlocal saved_count
        if routes:
            entries=routes[-1]['events']
            with (args.output/'events.jsonl').open('a',encoding='utf-8') as stream:
                for entry in entries[saved_count:]:stream.write(json.dumps(entry,ensure_ascii=False)+'\\n')
            saved_count=len(entries)
        if report['status']!='running':
            out=args.output/'01-真实父反馈四预算完整记录.json';temp=out.with_suffix('.tmp')
            temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(out)
""" + text[end:]
    path = WORKERS / ('reference_feedback.py' if no_quality else 'long_feedback.py')
    path.write_text(text, encoding='utf-8')
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    started = perf_counter()
    manifest_path = ROOT / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    identity = json.loads((WORKERS / 'build_identity.json').read_text(encoding='utf-8'))
    # 核查实际原生库及原始依赖；不替换另一任务的共享版本。
    for library in identity['libraries']:
        if sha(library['path']) != library['sha256']:
            raise ValueError('实际编译依赖摘要变化')
    binding = dict(time_beijing=now(),manifest_sha256=sha(manifest_path),budget_ms=200,
        complete_short_repair=json.loads((ROOT/'run_config.json').read_text())['complete_short_repair'],
        geogram_simplify=json.loads((ROOT/'run_config.json').read_text()).get('geogram_simplify',False),
        cancel_opposed_after_repair=json.loads((ROOT/'run_config.json').read_text()).get('cancel_opposed_after_repair',False),
        cluster_source_fallback=json.loads((ROOT/'run_config.json').read_text()).get('cluster_source_fallback',False),
        cluster_tolerance_mm=json.loads((ROOT/'run_config.json').read_text()).get('cluster_tolerance_mm',1e-10),
        source_certificate_override=json.loads((ROOT/'run_config.json').read_text()).get('source_certificate_override'),
        source_cleanup_sha256=sha(ROOT/'resident_source_cleanup.py') if (ROOT/'resident_source_cleanup.py').exists() else None,
        method={p.name:sha(p) for p in WORKERS.iterdir() if p.suffix in ('.py','.cpp','.so','.json')},
        worker_sha256=sha(__file__),build_identity=identity,geometry_policy='report_only_no_distance_stop',
        mode='常驻CPU材料更新和精确检查，CUDA活动边准备；无完整PaMO或安全投影',
        reference_policy='独立从原初态与全部原扫掠工具顺序更新，关闭可选质量翻边；共享必要修复，非算法独立真值',
        timing_scope='输入已预加载；在线数组可用时间含切削、必要修复、增量认证、CUDA维护及数组复制；离线文件保存另计',
        queue_scope='按实测在线服务时间计算虚拟FIFO；不是实际输入线程或屏幕显示测量')
    write(ROOT / '01-常驻长序列运行绑定.json',binding)
    report = dict(time_beijing=now(),status='running',planned_candidate_events=sum(len(r['prefix_tools']) for r in manifest['routes']),runs=[])
    write(ROOT / '02-常驻长序列完整记录.json',report)
    modules = {False:adapt(False),True:adapt(True)}
    binding['generated_entry_sha256']={name:sha(WORKERS/name) for name in ('long_feedback.py','reference_feedback.py')}
    write(ROOT / '01-常驻长序列运行绑定.json',binding)
    for route in manifest['routes']:
        initial = ROOT / 'inputs' / route['initial_mesh']
        if sha(initial) != route['initial_mesh_sha256']:raise ValueError('初态变化')
        tools = []
        for tool in route['prefix_tools']:
            path = ROOT / 'inputs' / tool['mesh']
            if sha(path) != tool['sha256']:raise ValueError('原扫掠工具变化')
            tools.append(dict(tool_path=str(path),tool_sha256=tool['sha256'],parent_path=str(initial),parent_sha256=sha(initial)))
        record_path = ROOT / (route['id'] + '_inputs.json')
        write(record_path,dict(routes=[dict(complete=True,events=tools)]))
        for reference in (False, True):
            label = route['id'] + ('_reference' if reference else '_candidate')
            output = ROOT / label
            captures = [];publication_rows=[]
            def capture(raw,source,arrays,event,published):
                snapshots = {'raw':tuple(a.copy() for a in raw),'source':tuple(a.copy() for a in source)}
                if published:snapshots['output']=tuple(a.copy() for a in arrays)
                elapsed = (perf_counter()-event['tool_arrival_perf_counter'])*1000 if published else event['cut_and_maintenance_ms']
                publication_rows.append(dict(step=event['step'],published=published,online_array_ready_ms=elapsed,
                    cut_and_maintenance_ms=event['cut_and_maintenance_ms'],maintenance_ms=event['maintenance_total_ms'],
                    boolean_ms=event['boolean']['total_ms']))
                captures.append((event['step'],snapshots))
                print(json.dumps(dict(run=label,step=event['step']+1,status=event['status'],online_ms=round(elapsed,3)),ensure_ascii=False),flush=True)
            def publish(v,f,bits,tv,tf,event):
                capture(publish.raw,publish.source,(v,f,bits),event,True)
            publish.failure = lambda raw,source,event:capture(raw,source,None,event,False)
            sys.argv=[__file__,'--ct-record',str(record_path),'--output',str(output),'--budgets','200',
                      '--fixed-flip-certificate','--early-quality-return','--edge-backend','cuda','--certified-operand-pairs']
            run_start = perf_counter();modules[reference].main(publisher=publish)
            active_wall = (perf_counter()-run_start)*1000
            ledger = json.loads((output / '01-真实父反馈四预算完整记录.json').read_text())
            write(output / '02-数组交付时间.json',publication_rows)
            # 实际原始源、修复源和发布数组逐件封存；这段是离线保存时间。
            save_start = perf_counter();saved=[]
            for step,snapshots in captures:
                for kind,arrays in snapshots.items():
                    path=output/f'e{step:03d}_{kind}.npz'
                    np.savez_compressed(path,vertices=arrays[0],faces=arrays[1],bits=arrays[2])
                    saved.append(dict(step=step,kind=kind,path=str(path),sha256=sha(path)))
            write(output / '03-保存数组清单.json',saved)
            rows=ledger['routes'][0]['events'];counts=dict(Counter(e['status'] for e in rows))
            run=dict(route=route['id'],reference=reference,planned=len(tools),statuses=counts,
                     output=str(output),active_wall_ms=active_wall,offline_save_ms=(perf_counter()-save_start)*1000,
                     ledger_sha256=sha(output/'01-真实父反馈四预算完整记录.json'))
            report['runs'].append(run);write(ROOT / '02-常驻长序列完整记录.json',report)
            print(json.dumps(run,ensure_ascii=False),flush=True)
    statistics=[]
    for run in report['runs']:
        rows=json.loads((Path(run['output'])/'02-数组交付时间.json').read_text())
        good=[e for e in rows if e['published']]
        times=np.array([e['online_array_ready_ms'] for e in good]);queue=[]
        if len(times):
            for hz in (1,2,5,10):
                finish=0;delays=[]
                for i,service in enumerate(times):
                    arrival=i*1000/hz;finish=max(finish,arrival)+service;delays.append(finish-arrival)
                queue.append(dict(input_hz=hz,model='虚拟FIFO，每个原扫掠工具逐件处理，不合并或丢弃',
                                  final_latency_ms=delays[-1],max_latency_ms=max(delays)))
        statistics.append(dict(route=run['route'],reference=run['reference'],statuses=run['statuses'],
            measured_published=len(good),mean_ms=float(times.mean()) if len(times) else None,
            p95_ms=float(np.percentile(times,95)) if len(times) else None,max_ms=float(times.max()) if len(times) else None,
            virtual_fifo=queue))
    report.update(status='completed_with_recorded_failures' if any(r['statuses'].get('source_rejected') for r in report['runs']) else 'completed',
                  finished_beijing=now(),total_wall_ms=(perf_counter()-started)*1000)
    write(ROOT/'02-常驻长序列完整记录.json',report)
    write(ROOT/'03-在线阶段统计与输入积压.json',dict(time_beijing=now(),runs=statistics,binding_sha256=sha(ROOT/'01-常驻长序列运行绑定.json')))


if __name__ == '__main__':
    main()
