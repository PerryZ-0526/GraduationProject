"""新评价输入在569号方法封存后一次生成；不得按结果改动本方法。"""
from pathlib import Path

here=Path(__file__).resolve().parent
source=(here/'441-冻结方法后独立新参数十六输入生成.py').read_text('utf8')
replacements=[
 ('440-固定原生主候选方法封存清单','569-新边拒绝原生主候选完整开发终态封存清单'),
 ('frozen_native_method_before_new_parameter_evaluation','frozen_native_method_after_complete_seen_development_before_future_new_evaluation'),
 ('共面前清理固定原生候选封存','新边拒绝固定原生候选封存'),
 ('固定方法新参数十六输入封存','新边拒绝固定方法第二批新参数十六输入封存'),
 ('seed=2026100701','seed=2026100704'),
 ('(113,.205,.039),(589,.298,.057),(863,.383,.089),(1241,.463,.105)',
  '(207,.219,.042),(631,.317,.062),(927,.407,.093),(1099,.491,.113)'),
 ('rng.uniform(4.6,5.6)','rng.uniform(4.7,5.8)'),
 ('[.021,.043,.067]','[.026,.051,.074]'),('(2.3,1.7,width)','(2.41,1.83,width)'),
 ('[2.3,1.7,width]','[2.41,1.83,width]'),('.046+.004*i','.051+.0045*i'),
 ('[.023,.049,.079]','[.031,.057,.087]'),('(1.17,2.26,.93)','(1.23,2.17,1.07)'),
 ('(1.17+width)','(1.23+width)'),('.052+.003*i','.061+.0037*i'),('.93/2+.028+.003*i','1.07/2+.033+.0035*i'),
 ('(.025,.42),(.053,.47),(.083,.55)','(.031,.435),(.061,.495),(.097,.575)'),
 ('.047+.006*i','.053+.0065*i'),('minor+.031+.004*i','minor+.035+.0045*i'),
 ('(15207,.287,.044),(27631,.463,.083),(36173,.681,.101)',
  '(17031,.309,.052),(29407,.507,.095),(38763,.733,.119)'),
 ('391-原生十四同输入含第四刀断言负例冻结清单','526-新边拒绝三十已见输入回归冻结清单'),
 ('random_seed\':2026100702','random_seed\':2026100705'),
 ('442-固定方法新参数十六输入运行前冻结清单','574-新边拒绝固定方法第二批十六新参数运行前冻结清单')]
for old,new in replacements:
    assert old in source,old
    source=source.replace(old,new)
(here/'573-封存新边拒绝方法后第二批十六新参数生成.py').write_text(source,'utf8')
worker=(here/'444-固定原生方法十六新参数完整交错评价.py').read_text('utf8')
worker=worker.replace('frozen_native_method_before_new_parameter_evaluation','frozen_native_method_after_complete_seen_development_before_future_new_evaluation')
worker=worker.replace('第二十轮实际构建绑定候选修订','新边拒绝封存方法实际构建绑定候选修订')
(here/'575-新边拒绝固定方法第二批十六新参数完整交错评价.py').write_text(worker,'utf8')
controller=(here/'445-固定方法十六新参数评价上传取回.py').read_text('utf8')
for old,new in [('20261007_23','20261007_29'),('440-固定原生主候选方法封存清单','569-新边拒绝原生主候选完整开发终态封存清单'),('442-固定方法新参数十六输入运行前冻结清单','574-新边拒绝固定方法第二批十六新参数运行前冻结清单'),('444-固定原生方法十六新参数完整交错评价','575-新边拒绝固定方法第二批十六新参数完整交错评价'),('446-固定方法十六新参数评价实际取回记录','577-新边拒绝固定方法第二批十六新参数评价实际取回记录'),('447-固定方法十六新参数完整评价控制台日志','578-新边拒绝固定方法第二批十六新参数完整评价控制台日志'),('448-固定方法十六新参数全部实际输出','579-新边拒绝固定方法第二批十六新参数全部实际输出'),('449-固定方法新参数实际运行构建记录','580-新边拒绝固定方法第二批十六新参数实际运行构建记录')]:
    controller=controller.replace(old,new)
start=controller.index("        folder=here/'固定方法十六新参数全部实际输出'")
end=controller.index('        record.update(status=',start)
controller=controller[:start]+'''        # 完整ZIP先核对CRC，再直接读取终态账本，避免重复解包。
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            worker=json.loads(z.read('01-固定方法十六新参数交错质量速度记录.json'))
'''+controller[end:]
(here/'576-新边拒绝固定方法第二批十六新参数上传取回.py').write_text(controller,'utf8')
recompute=(here/'556-新边拒绝三十已见原始压缩包直接复算.py').read_text('utf8')
recompute=recompute.replace("wrapped=json.loads(ap.read_text('utf8'))","wrapped=json.loads(archive.read(ap.relative_to(folder).as_posix()))")
for old,new in [('新边拒绝三十已见回归全部实际输出','新边拒绝固定方法第二批十六新参数全部实际输出'),('531-新边拒绝固定方法第二批十六新参数全部实际输出','579-新边拒绝固定方法第二批十六新参数全部实际输出'),('01-新边拒绝三十已见输入交错质量速度记录','01-固定方法十六新参数交错质量速度记录'),('526-新边拒绝三十已见输入回归冻结清单','574-新边拒绝固定方法第二批十六新参数运行前冻结清单'),('508-递归前机器新边拒绝版本源码清单','569-新边拒绝原生主候选完整开发终态封存清单'),('completed_all_thirty_seen_development_planned_attempts','completed_all_fixed_method_new_parameter_planned_attempts'),('534-新边拒绝三十已见输入完整复算','582-新边拒绝固定方法第二批十六新参数完整复算'),('420','224'),('==60','==32'),('==30','==16'),('新方法运行前固定，全部输入已见，不声称独立评价','方法在新参数生成前封存，不根据该评价修改本方法')]:
    recompute=recompute.replace(old,new)
(here/'581-新边拒绝固定方法第二批新参数原归档完整复算.py').write_text(recompute,'utf8')
worker=(here/'453-固定方法新参数全部返回保存对象精确复审.py').read_text('utf8')
(here/'583-新边拒绝固定方法第二批全部保存精确复审.py').write_text(worker,'utf8')
controller=(here/'454-固定方法新参数保存精确复审上传取回.py').read_text('utf8')
for old,new in [('20261007_23','20261007_29'),('453-固定方法新参数全部返回保存对象精确复审','583-新边拒绝固定方法第二批全部保存精确复审'),('455-固定方法新参数保存精确复审实际取回记录','585-新边拒绝固定方法第二批保存精确复审实际取回记录'),('456-固定方法新参数保存精确复审控制台日志','586-新边拒绝固定方法第二批保存精确复审控制台日志'),('457-固定方法新参数保存精确复审全部输出','587-新边拒绝固定方法第二批保存精确复审全部输出'),('固定方法十六新参数全部保存准确复审','新边拒绝固定方法第二批十六新参数全部保存准确复审')]:controller=controller.replace(old,new)
(here/'584-新边拒绝固定方法第二批保存精确复审取回.py').write_text(controller,'utf8')
print('prepared_future_new_parameter_evaluation')
