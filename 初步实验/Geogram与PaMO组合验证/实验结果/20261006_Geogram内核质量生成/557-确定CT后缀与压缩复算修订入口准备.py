"""只续跑经原账本证实未执行的末刀，完整归档不覆盖原进程。"""
from pathlib import Path

here=Path(__file__).resolve().parent
source=(here/'543-新边拒绝原生CT十六刀候选反馈与同父参照.py').read_text('utf8')
source=source.replace("folder=root/'native_ct16_feedback_01';folder.mkdir()","folder=root/'native_ct16_feedback_recovery_02';folder.mkdir()")
anchor='save()\ntry:\n    initial='
prefix='''# 十五刀原始账本已经终止；只继续第十六刀，原文件保持。
prefix_path=root/'native_ct16_feedback_01/01-原生CT十六刀反馈实际记录.json'
prefix=json.loads(prefix_path.read_text('utf8'))
assert prefix['status']=='failed_actual_native_feedback_controller' and prefix.get('error')=='[Errno 32] Broken pipe'
assert len(prefix['events'])==15 and all(e['status']=='accepted_native_output' for e in prefix['events'])
assert prefix['build_sha256']==record['build_sha256'] and prefix['manifest_sha256']==record['manifest_sha256']
for event in prefix['events']:
    assert sha(Path(event['parent_path']))==event['parent_sha256']
    for value in event['methods'].values():
        if value['returncode']==0:
            assert sha(Path(value['mesh_path']))==value['mesh_sha256']
            assert sha(Path(value['audit']['path']))==value['audit']['sha256']
record.update(events=prefix['events'],source_prefix_record_sha256=sha(prefix_path),verified_copied_prefix_events=15,
    recovery_policy='仅新增第十六刀实际调用；十五刀原记录保持；原进程不称正常完整终态')
save()
try:
    initial='''
assert source.count(anchor)==1;source=source.replace(anchor,prefix)
source=source.replace('parent=initial;blocked=False;',"parent=Path(prefix['events'][-1]['methods']['candidate']['mesh_path']);blocked=False;")
source=source.replace("    for i,tool in enumerate(manifest['tools']):\n        row=","    for i,tool in enumerate(manifest['tools']):\n        if i<15:continue\n        row=")
source=source.replace("root/'native_ct16_feedback_01.zip'","root/'native_ct16_feedback_recovery_02.zip'")
anchor='        for p in folder.iterdir():archive.write(p,p.name)'
assert source.count(anchor)==1
source=source.replace(anchor,'''        for p in folder.iterdir():archive.write(p,p.name)
        # 原前缀逐字节加入完整新归档，同名预审必须一致，不再生成前十五刀。
        existing=set(archive.namelist())
        for p in prefix_path.parent.iterdir():
            if not p.is_file():continue
            if p==prefix_path:
                archive.write(p,'02-中断前原始十五刀前缀记录.json')
            elif p.name not in existing:
                archive.write(p,p.name)
            else:
                assert sha(p)==sha(folder/p.name)''')
(here/'558-新边拒绝CT只恢复确定未执行末刀.py').write_text(source,'utf8')
controller=(here/'544-新边拒绝原生CT十六刀反馈上传取回.py').read_text('utf8')
controller=controller.replace("'mkdir '+root+'/ct16_inputs'","'test -d '+root+'/ct16_inputs'")
for old,new in [('543-新边拒绝原生CT十六刀候选反馈与同父参照','558-新边拒绝CT只恢复确定未执行末刀'),('545-新边拒绝原生CT十六刀实际执行取回记录','560-新边拒绝CT确定后缀恢复实际取回记录'),('546-新边拒绝原生CT十六刀实际控制台日志','561-新边拒绝CT确定后缀恢复控制台日志'),('547-新边拒绝原生CT十六刀全部实际输出','562-新边拒绝CT确定后缀完整归档'),('native_ct16_feedback_01.zip','native_ct16_feedback_recovery_02.zip')]:controller=controller.replace(old,new)
start=controller.index("        output=here/'新边拒绝原生CT十六刀全部实际输出'")
end=controller.index('        record.update(status=',start)
controller=controller[:start]+'''        # 从完整压缩归档读取终态账本，不重复解包。
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            worker=json.loads(z.read('01-原生CT十六刀反馈实际记录.json'))
'''+controller[end:]
(here/'559-新边拒绝CT确定后缀恢复上传取回.py').write_text(controller,'utf8')
source=(here/'556-新边拒绝三十已见原始压缩包直接复算.py').read_text('utf8')
source=source.replace("wrapped=json.loads(ap.read_text('utf8'))","wrapped=json.loads(archive.read(ap.relative_to(folder).as_posix()))")
source=source.replace('534-新边拒绝三十已见输入完整复算','565-新边拒绝三十已见原归档完整复算')
(here/'564-新边拒绝三十已见原归档全字段复算.py').write_text(source,'utf8')
print('prepared_final_unexecuted_event_and_zip_audit_reader')
