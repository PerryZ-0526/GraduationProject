"""准备固定方法十六例完整分母评价，生成失败也继续后续计划，不剔除案例。"""
from pathlib import Path
here=Path(__file__).resolve().parent
worker=(here/'392-共面前清理原生十四输入完整交错评价.py').read_text('utf8')
worker=worker.replace('原生十四同输入','固定方法十六新参数').replace("record['planned_native_benchmark_attempts'] = 196","record['planned_native_benchmark_attempts'] = 224")
# 正式新参数评价不再生成诊断轨迹或修改方法；全部运行后另审计每张实际保存网格。
start=worker.index('    # 另作逐区域诊断')
end=worker.index("    record.update(status='completed_all_native_paired_development_runs'",start)
worker=worker[:start]+worker[end:]
worker=worker.replace("if process.returncode: raise RuntimeError('原生生成真实失败，完整保留失败记录')",
 "# 已记录的失败继续保留，后续不同输入仍按原计划执行。")
old="""        for method in ['baseline','candidate']:
            mesh=folder/(method+'_r00.obj')
            audit=subprocess.run"""
new="""        for method in ['baseline','candidate']:
            mesh=folder/(method+'_r00.obj')
            first=next(r for r in record['rows'] if r['case_index']==i and r['method']==method and r['repeat']==0)
            if first['returncode']!=0:continue
            audit=subprocess.run"""
assert old in worker;worker=worker.replace(old,new)
worker=worker.replace("    record.update(status='completed_all_native_paired_development_runs',finished_beijing=now())",
 """    assert len(record['rows'])==224
    record.update(status='completed_all_fixed_method_new_parameter_planned_attempts',finished_beijing=now(),
                  saved_outputs=sum(r['returncode']==0 for r in record['rows']),
                  failed_attempts=sum(r['returncode']!=0 for r in record['rows']))""")
# 冻结核对在读取方法及摘要工具之后执行；正式生成前核查两个库、两个可执行文件及三份实际源码。
marker="os.environ.pop('GEO_NATIVE_QUALITY_TRACE',None)"
binding="""
fixed=json.loads((root/'fixed_method.json').read_text('utf8'))
assert fixed['status']=='frozen_native_method_before_new_parameter_evaluation'
native_root=Path(fixed['method']['remote_root'])
assert sha(native_root/'build_record.json')==fixed['method']['build_sha256']
assert sha(native_root/'source_manifest.json')==fixed['method']['source_manifest_sha256']
for method in ['baseline','candidate']:
    assert sha(root/method)==fixed['method'][method+'_binary_sha256']
assert sha(native_root/'candidate_build/lib/libgeogram.so')==fixed['method']['candidate_library_sha256']
assert sha(Path('/tmp/geogram_native_quality_20261006_02/baseline_build/lib/libgeogram.so'))==fixed['method']['baseline_library_sha256']
for name,digest in fixed['files'].items():
    if name.startswith('mesh_surface_'):
        assert sha(native_root/'candidate_source/src/lib/geogram/mesh'/name)==digest
assert sha(root/'fixed_method.json')==manifest['method_manifest_sha256']
"""
assert marker in worker;worker=worker.replace(marker,marker+binding,1)
old="""try:
    for i,case in enumerate(manifest['cases']):"""
new="""try:
    # 全部输入在第一份生成结果出现前准确核查，预审也绑定原冻结摘要。
    for i,case in enumerate(manifest['cases']):
        parent=root/'inputs'/f'{i:02d}_parent.obj'
        tool=root/'inputs'/f'{i:02d}_tool.obj'
        assert sha(parent)==case['parent_sha256'] and sha(tool)==case['tool_sha256']
        for role,mesh in [('parent',parent),('tool',tool)]:
            audit=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
            result=json.loads(audit.stdout) if audit.returncode==0 else None
            entry={'case_index':i,'role':role,'mesh_sha256':sha(mesh),'returncode':audit.returncode,
                   'stdout':audit.stdout,'stderr':audit.stderr}
            record.setdefault('input_preflight',[]).append(entry);save()
            assert result and result['embedded_closed']
    for i,case in enumerate(manifest['cases']):"""
assert old in worker;worker=worker.replace(old,new)
(here/'444-固定原生方法十六新参数完整交错评价.py').write_text(worker,'utf8')
print('prepared_fixed_method_all_224_planned_attempts_without_diagnostic_tuning')
