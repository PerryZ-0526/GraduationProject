"""核对终态证据后记录实际收益与速度差距，不把研究候选称为完成。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
parent=here.parents[1]
project=here.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
summary_path=here/'237-邻接索引修订原生十一同输入完整复算.json'
summary=json.loads(summary_path.read_text('utf8'))
assert summary['status']=='completed_all_154_saved_quality_recomputations_and_eleven_geometry_timing_pairs'
assert len(summary['all_repeat_quality'])==154 and len(summary['cases'])==11
folder=here/'第十四轮邻接索引修订原生全部重复与诊断输出'
record_path=folder/'01-原生十一同输入交错质量速度记录.json'
record=json.loads(record_path.read_text('utf8'))
assert sha(record_path)==summary['source_record_sha256']
assert record['status']=='completed_all_native_paired_development_runs'
assert len(record['rows'])==154 and len(record['native_audits'])==22
assert len(record['generation_traces'])==11 and len(record['raw_stage_audits'])==2
additional=[]
# 对附加保存审计逐字节核对，不将22份首审混称154次全量准确检查。
for i in range(11):
    path=folder/f'{i:02d}'/'candidate_trace_native_audit.json'
    trace=next(r for r in record['generation_traces'] if r['case_index']==i)
    assert sha(path)==trace['audit_sha256']
    audit=json.loads(path.read_text('utf8'))
    assert audit['returncode']==0 and json.loads(audit['stdout'])['embedded_closed']
    additional.append(path.name)
for i in [9,10]:
    path=folder/f'{i:02d}'/'candidate_no_simplify_native_audit.json'
    raw=next(r for r in record['raw_stage_audits'] if r['case_index']==i)
    assert sha(path)==raw['audit_sha256']
    audit=json.loads(path.read_text('utf8'))
    assert audit['returncode']==0 and json.loads(audit['stdout'])['embedded_closed']
    additional.append(path.name)
build=json.loads((here/'229-邻接索引修订实际原生编译记录.json').read_text('utf8'))
manifest=json.loads((here/'224-共边邻接索引成本修订源码清单.json').read_text('utf8'))
assert build['status']=='completed_candidate_build_with_verified_original_baseline_reuse'
assert build['source_manifest_sha256']==sha(here/'224-共边邻接索引成本修订源码清单.json')
for name,digest in manifest['files'].items():
    assert sha(here/'第十四轮共边邻接索引成本修订'/name)==digest
    assert build['candidate_source_hashes']['src/lib/geogram/mesh/'+name]==digest
changed=[name for name,digest in build['baseline_source_hashes'].items() if build['candidate_source_hashes'][name]!=digest]
assert sorted(changed)==sorted('src/lib/geogram/mesh/'+name for name in manifest['files'])
names=['普通切口00','普通切口01','普通切口02','薄壁0.018毫米','薄壁0.036毫米',
       '窄缝0.018毫米','窄缝0.036毫米','孔0.018毫米','孔0.036毫米','CT首刀父输入','CT旧末刀父输入']
rows=[]
for c,name in zip(summary['cases'],names):
    b=c['methods']['baseline'];a=c['methods']['candidate']
    assert a['first_output_embedded_closed']
    rows.append(f"|{name}|{b['quality']['below_10_faces']}→{a['quality']['below_10_faces']}|"
                f"{b['boolean_timing']['median_ms']:.3f}→{a['boolean_timing']['median_ms']:.3f}|"
                f"{a['repeat_quality_ranges']['below_10_faces']['min']}—{a['repeat_quality_ranges']['below_10_faces']['max']}|"
                f"{a['quality']['faces']}|")
peak=max(c['geometry'][d]['area_max_mm'] for c in summary['cases'] for d in ['baseline_to_candidate','candidate_to_baseline'])
now=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日 %H:%M:%S')
report=parent/'215-Geogram内核一致共边生成质量突破与速度剩余差距.md'
assert not report.exists()
text=f'''# Geogram内核一致共边生成质量突破与速度剩余差距

生成时间：{now}（北京时间）

修改时间及修改内容：{now}（北京时间），首次汇总内核共边生成突破、完整重复评价、失败链及实际速度差距。

文档概述：Geogram内部直接生成的两孔差面减少约98%，薄壁和窄缝降至零；当前第十四轮完整评价结束，但原版速度仍未保住，CT及普通切口收益有限，整体目标继续。

索引目录：1.版本与方法；2.当前完整结果；3.原因和负例；4.速度定位；5.证据与复现；6.完成范围。

## 1. 版本与方法

206、212号都是本任务此前做出的外部维护产物。213号起才直接修改Geogram内部生成。本轮所有正式比较均为原生`mesh_boolean_operation(A-B)`返回网格，不接Python维护、PaMO或GPU。原版是实例Geogram 1.10.2-rc，与本次旧研究版严格区分。

当前第十四轮在区域三角化阶段对规则细长凸四边形生成一致二分条带：边端点按全局编号统一排序，用准确端点和二分参数生成边点，不再让两侧各自选择近重合的浮点点。每区域最多64条带、126新增边点；15度是条带尺寸设计参数，不是所有输出的角度保证。其他区域仍使用既有有界细化。机器尺度非准确共面只开放给共享原边的凸四边形。

共边同步后核对完整候选；合格时跳过第二次全网格准确CDT，不合格时仍执行既有再生成与回退。局部及整体差面数量、绝对差面面积和零面积检查不放宽。第十四轮只优化共边邻接查询容器，面和边处理顺序保持。逐文件核对原版与候选的{len(build['baseline_source_hashes'])}份源文件，仅三份生成阶段文件不同，Triangle原源码未改。

## 2. 当前完整十一输入结果

固定18号清单全部是已见开发输入，保留旧名字中的“未见”字样不代表独立评价。每方法预热一次、测量六次、交错执行；完整154次主调用成功且154份保存质量全部独立复算。候选首份11/11闭合准确嵌入通过，额外十一轨迹和两禁简化保存对象13/13通过。只有这些保存对象作了EPECK全量静态检查，不冒称154次全部重复都作了准确检查。

|输入|首份小于10度面数原版→候选|同轮内核中位毫秒原版→候选|候选六次差面范围|首份候选总面数|
|---|---:|---:|---:|---:|
'''+'\n'.join(rows)+f'''

两孔分别1781→29、1781→27，减少约98.37%、98.48%；面积也明显下降。两薄壁50→0，两窄缝42→0。普通切口仅部分改善，CT首刀796→768、旧末刀634→585，不能由孔与薄壁结果宣称所有形状均大幅改善。条带增加总面数，两孔约4.6万和2.7万面，输出规模和成本均保留。

双向各8192面积样本及全部顶点探针已记录，当前十一例面积样本最大距离约{peak:.6g}毫米。237号保留多个距离覆盖比例和分位数，不新增固定0.1毫米峰值或固定比例要求。这是与同输入原版的离散比较，不是一般连续误差证书。

## 3. 真实诊断与负结果

第七轮已完整跑154输出，窄缝42→0、薄壁50→8，但孔1781不变。第八轮广泛开放边界补点，实际142尝试141保存；确认CT旧末刀单次CPU超过414秒后人为SIGABRT终止，无堆栈，不伪称自然崩溃。141份保存对象已全部复算，失败原账本保留于167号。独立指令采样仅定位到准确CDT谓词缓存插入，不能据此声称已经证明根因。

第六轮诊断副本捕获第五轮实际Triangle失败区域：原23个二维点互不重合，浮点细化新产生重合点、非法队列键0并失败。实际区域重放说明窄缝128点预算能比64预算取得更好结果；214号依据“最终保留不足64点”排除预算因素的推断不再成立，因为生成器预算与最终保留点数并非等价。

第十轮机器尺度分组与广泛细化完整执行，但孔仅少十几张差面、耗时达原版约16—20倍，CT末刀差面增加；不交付这个失败候选。真实判定前对象捕获进一步发现孔共边673个机器精度级短段、404张零面积面，未接受对象4896差面。第十二轮一致二分条带解决主要重复补点问题，主评价154份保存完成，孔1781→39/37；附加日志被并行条带打印污染而解析失败，原失败终态保留。第十三轮移除冲突打印，完整主评价、附加诊断全部通过，孔29/27。第十四轮再次完整验证，保留这个质量水平。

## 4. 速度定位与剩余代价

当前六次中位耗时及完整范围见237号。薄壁、窄缝约几十毫秒，孔约数百毫秒，CT约一至一点五秒；与同轮原版相比，多数仍明显更慢，不能称已保证速度，更不能用共享实例中偶然较快的个例宣称加速。正式计时不含加载、保存、准确检查、抽样审计、SSH和诊断日志成本。

第十三轮独立开启作者原有阶段计时的12次调用显示，孔候选共面生成约0.285秒，原版约0.029秒；CT首刀候选共面生成0.818秒（包含0.334秒递归），原版0.278秒。旧末刀候选共面生成1.059秒（递归0.405秒），原版0.310秒。这些单次带日志诊断不混入正式速度分布，也不能单独证明某容器就是唯一瓶颈。

第十四轮哈希邻接索引未改变质量，但整体速度改善仍不足。下一步应减少共边再生成中未受影响区域的准确CDT重建，并测量点提交、共边同步与生成本身的分项成本；不降低质量检查来取得速度数字。

## 5. 证据与复现范围

全部证据在`实验结果/20261006_Geogram内核质量生成`：224号冻结三源码、229号实际构建、231/232号完整评价入口、233号执行取回、235号完整保存归档、236/237号154质量及几何速度复算。源目录为`第十四轮共边邻接索引成本修订`，准确诊断依赖摘要与运行库绑定在原记录中。原输入22文件另存于可复用原生内核开发输入目录，不能恢复为新评价输入。

实际远端目录为`/tmp/geogram_native_quality_20261006_15`。原生执行器调用形式为`candidate parent.obj tool.obj output.obj`；原版基线只读复用。编译配置见225号和229号，包含同配置Release和Triangle支持；已有Geogram依赖及CGAL准确检查器仍需原环境，不声明独立可移植安装包。带轨迹需显式开启`GEO_NATIVE_QUALITY_TRACE=1`，轨迹耗时不计正式速度。已有批次入口有不可覆盖检查，不直接重跑原目录覆盖证据。

## 6. 当前完成范围

本轮取得真实内核质量突破，不能当作目标已经完成。尚需：在保留质量的条件下降低实际生成代价；改进CT及普通切口的有限收益；冻结候选后作新的独立输入和原生连续切削验证；交付可复现源码补丁与完整统计。此前外部维护的连续结果不能代替本内核的连续验证。GPU实例保持开启。
'''
report.write_text(text,'utf8')
root=project/'研究内容1-创新点.md'
backup=here/'239-一致共边内核汇总前研究内容原文快照.md';assert not backup.exists()
backup.write_bytes(root.read_bytes())
prefix=f'''> **Geogram原生内核进展（215号）**：{now}（北京时间）。一致二分共边第十四轮完整154输出复算，候选首份11/11、附加13/13准确嵌入通过；两孔1781→29/27，薄壁50→0，窄缝42→0。孔质量减少约98%，但速度仍慢于原版，CT及普通切口收益有限，整体目标继续。详见[215号结果](初步实验/Geogram与PaMO组合验证/{report.name})。
>
> **生成时间**：{now}（北京时间）；**修改时间及修改内容**：{now}（北京时间），追加真实内核收益及速度差距；**文档概述**：生成结果已取得部分大幅质量改善，速度尚未完成；**索引目录**：版本身份、当前质量、成本及后续验证。

'''
root.write_text(prefix+backup.read_text('utf8'),'utf8')
print(json.dumps({'status':'verified_progress_report_saved_goal_not_complete','report':str(report),
                  'candidate_first_native':11,'additional_native':len(additional),
                  'saved_repeat_quality':154,'changed_native_sources':changed},ensure_ascii=False))
