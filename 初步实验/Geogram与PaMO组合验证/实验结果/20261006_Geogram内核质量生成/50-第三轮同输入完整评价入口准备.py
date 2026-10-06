"""绑定第三轮构建，复用固定输入与交错计时，另外保存非计时生成轨迹。"""
from pathlib import Path

here=Path(__file__).resolve().parent
worker=(here/'19-远端原生同输入交错质量速度对照.py').read_text('utf8')
worker=worker.replace("build_record_03.json","build_record.json").replace("completed_two_isolated_native_builds","completed_candidate_build_with_verified_original_baseline_reuse")
worker=worker.replace("# 同配置显式TBB链接恢复记录是本次实际执行的原版及候选构建。","# 第三轮实际构建绑定候选修订，原版基线只读复用并核对。")
needle="os.sched_setaffinity(0,selected)"
worker=worker.replace(needle,needle+"\n# 正式耗时排除开发轨迹输出，轨迹只在后面的单独调用开启。\nos.environ.pop('GEO_NATIVE_QUALITY_TRACE',None)")
worker=worker.replace("'native_audits':[]}","'native_audits':[],'generation_traces':[],'raw_stage_audits':[]}")
needle="    record.update(status='completed_all_native_paired_development_runs',finished_beijing=now())"
assert worker.count(needle)==1
worker=worker.replace(needle,"""    # 另作逐区域诊断，其生成与准确检查成本不进入上面的速度分布。
    for i,case in enumerate(manifest['cases']):
        folder=output/f'{i:02d}'
        mesh=folder/'candidate_trace.obj'
        env=dict(os.environ,GEO_NATIVE_QUALITY_TRACE='1')
        p=subprocess.run([str(root/'candidate'),str(root/'inputs'/f'{i:02d}_parent.obj'),
                          str(root/'inputs'/f'{i:02d}_tool.obj'),str(mesh)],
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env)
        log=folder/'candidate_trace.log';log.write_text(p.stdout,'utf8')
        traces=[json.loads(line[len('NATIVE_QUALITY_REGION '):]) for line in p.stdout.splitlines()
                if line.startswith('NATIVE_QUALITY_REGION ')]
        assert p.returncode==0
        audit=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ap=folder/'candidate_trace_native_audit.json'
        ap.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr},
                                ensure_ascii=False,indent=2)+'\\n','utf8')
        record['generation_traces'].append({'case_index':i,'case':case['id'],'returncode':p.returncode,
            'mesh_sha256':sha(mesh),'log_sha256':sha(log),'audit_sha256':sha(ap),'regions':traces,
            'zero_edge_log':[line for line in p.stdout.splitlines() if 'contracted_zero_length_edges=' in line]})
        save();print('trace',i,len(traces),sum(t['selected'] for t in traces),flush=True)
    # 真实CT另跑禁共面简化，检查零长度收缩本身是否修复原始交线阶段。
    for i in [9,10]:
        folder=output/f'{i:02d}';mesh=folder/'candidate_no_simplify.obj'
        p=subprocess.run([str(root/'candidate'),str(root/'inputs'/f'{i:02d}_parent.obj'),
                          str(root/'inputs'/f'{i:02d}_tool.obj'),str(mesh),'no-simplify'],
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        log=folder/'candidate_no_simplify.log';log.write_text(p.stdout,'utf8');assert p.returncode==0
        audit=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ap=folder/'candidate_no_simplify_native_audit.json'
        ap.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr},
                                ensure_ascii=False,indent=2)+'\\n','utf8')
        record['raw_stage_audits'].append({'case_index':i,'mesh_sha256':sha(mesh),'log_sha256':sha(log),
                                         'audit_sha256':sha(ap),'returncode':p.returncode})
        save()
"""+needle)
(here/'51-第三轮远端原生交错评价与生成诊断.py').write_text(worker,'utf8')
# 逐字节相同的输入仍为开发输入；本轮单独目录保存全部重复和失败。
auditor=(here/'24-全部重复输出质量与同源几何复算.py').read_text('utf8')
auditor=auditor.replace("folder=here/'原生同输入全部重复输出'","folder=here/'第三轮原生全部重复与诊断输出'")
auditor=auditor.replace("25-原生十一同输入质量几何与速度复算.json","57-第三轮原生十一同输入质量几何与速度复算.json")
(here/'56-第三轮全部重复质量几何与速度复算.py').write_text(auditor,'utf8')
print('第三轮完整固定输入评价与轨迹入口已准备')
