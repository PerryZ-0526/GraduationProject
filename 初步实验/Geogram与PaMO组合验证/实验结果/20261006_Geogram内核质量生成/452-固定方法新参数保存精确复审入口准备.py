"""对全部实际返回保存对象准确审计，224计划里的执行失败仍保留完整分母。"""
from pathlib import Path
here=Path(__file__).resolve().parent
worker=(here/'399-十四输入全部196保存重复精确复审.py').read_text('utf8')
worker=worker.replace('原生十四同输入','固定方法十六新参数')
worker=worker.replace("assert original['status']=='completed_all_native_paired_development_runs'",
                      "assert original['status']=='completed_all_fixed_method_new_parameter_planned_attempts'")
worker=worker.replace("assert len(original['rows'])==196 and all(r['returncode']==0 for r in original['rows'])",
 "assert len(original['rows'])==224\nreturned=[r for r in original['rows'] if r['returncode']==0]")
worker=worker.replace("'planned':196,'rows':[]","'planned':len(returned),'planned_attempts':224,'rows':[]")
worker=worker.replace("01-全部196保存对象准确复审记录.json","01-224计划实际保存对象准确复审记录.json")
worker=worker.replace("for row in original['rows']]):","for row in returned]):")
worker=worker.replace("assert len(record['rows'])==196","assert len(record['rows'])==len(returned)")
worker=worker.replace("completed_all_196_saved_object_exact_audits","completed_all_saved_objects_from_224_planned_attempts_exact_audits")
# 汇总以完整112次计划为每方法分母，同时分别保留返回及嵌入数量。
worker=worker.replace("'total':sum(r['method']==m for r in record['rows']),",
 "'planned_attempts':112,'total':sum(r['method']==m for r in record['rows']),")
(here/'453-固定方法新参数全部返回保存对象精确复审.py').write_text(worker,'utf8')
controller=(here/'400-全部196保存重复精确复审上传取回.py').read_text('utf8')
for a,b in [('20261006_21','20261007_23'),
 ('399-十四输入全部196保存重复精确复审.py','453-固定方法新参数全部返回保存对象精确复审.py'),
 ('401-全部196重复精确复审实际取回记录.json','455-固定方法新参数保存精确复审实际取回记录.json'),
 ('402-全部196重复精确复审控制台日志.txt','456-固定方法新参数保存精确复审控制台日志.txt'),
 ('403-全部196保存对象精确复审全部输出.zip','457-固定方法新参数保存精确复审全部输出.zip'),
 ('十四输入全部196保存重复准确复审','固定方法十六新参数全部保存准确复审'),
 ('01-全部196保存对象准确复审记录.json','01-224计划实际保存对象准确复审记录.json')]:controller=controller.replace(a,b)
(here/'454-固定方法新参数保存精确复审上传取回.py').write_text(controller,'utf8')
print('prepared_all_returned_objects_audits_with_full_224_denominator')
