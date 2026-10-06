"""在实际完整统计及全部重复准确审计成立后汇总，并保留研究入口原字节。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
parent=here.parents[1]
project=here.parents[3]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
summary_path=here/'359-逐轮修复原生十三同输入完整复算.json'
summary=json.loads(summary_path.read_text('utf8'))
assert summary['status']=='completed_all_182_saved_quality_recomputations_and_thirteen_geometry_timing_pairs'
assert len(summary['all_repeat_quality'])==182 and len(summary['cases'])==13
audits_path=here/'十三输入全部182保存重复准确复审/01-全部182保存对象准确复审记录.json'
audits=json.loads(audits_path.read_text('utf8'))
assert audits['status']=='completed_all_182_saved_object_exact_audits'
assert audits['totals']['candidate']=={'total':91,'embedded_closed':91}
feedback_path=here/'350-逐轮新边修复原生CT十六刀保存联合复算.json'
feedback=json.loads(feedback_path.read_text('utf8'))
assert feedback['status']=='completed_all_sixteen_events_saved_parent_chain_quality_geometry_recomputation'
assert feedback['totals']['accepted']==3 and feedback['totals']['rejected']==1 and feedback['totals']['blocked']==12
scene=json.loads((here/'368-原生第四刀准确共面断言复用资产清单.json').read_text('utf8'))
assert scene['failure']['returncode']==1
now=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日 %H:%M:%S')
report=parent/'216-Geogram原生十三输入完整质量速度统计与连续第四刀负例.md';assert not report.exists()
lines=[
'# Geogram原生十三输入完整质量速度统计与连续第四刀负例',
'',f'生成时间：{now}（北京时间）','',
f'修改时间及修改内容：{now}（北京时间），首次汇总第十五至十九轮、全部重复精确审计和原生十六刀拒绝。','',
'文档概述：当前第十九轮十三输入完整182次原生调用及质量复算完成，候选91/91保存网格准确嵌入；薄壁和窄缝差面归零、两孔差面减少约98.5%，普通切口和CT收益有限。速度按用户要求先报告完整分布，不设固定验收值。原生连续前三刀通过，第四刀准确共面三角化自然断言失败，整体目标仍未完成。','',
'索引目录：1.当前方法；2.完整质量；3.完整速度；4.保存几何与有效分母；5.连续负例和真实修复；6.证据、复现与下一步。','',
'## 1. 当前方法与身份','',
'206、212号是本任务此前的外部维护研究产物；213号起才改Geogram内部。本轮实际调用Geogram 1.10.2-rc的`mesh_boolean_operation(A-B)`，返回前完成区域质量生成和必要的机器尺度新边处理，不接Python维护或PaMO。当前方法是第十九轮，源码目录为`第十九轮新边收缩互斥邻域逐轮复查`，336号冻结三份源文件，341号绑定实际原运行库。','',
'保留一致二分共边条带、局部与全局差面数量/绝对差面面积检查，并限制第二次生成到共边改变的区域。末阶段收缩只允许机器尺度边，保护不同原输入坐标，保留流形链接条件、邻面正面积与法向不翻转；同轮一环互斥，各轮重新核查，实际面数下降才继续。算法中的机器尺度判据不等于用户的几何精度验收门槛。','',
'第十六、十七轮的“当前差面触发新增近共面分组”单独保留；第十八轮恢复第十五轮分组来隔离因素，第十九轮只增加跨轮重查，不把两个改动混成单因素归因。','',
'## 2. 完整十三输入质量','',
'352号全部是已见开发输入；名称中的旧“未见”标签不恢复独立评价身份。原十一例不变，追加第二刀自交负例和前版本新父第二刀超时负例。每方法一预热、六测量，交错执行，共182次主调用成功，182张保存网格均独立复算质量。','',
'下表是各方法首份实际输出，数量和绝对面积同时报告，不能只靠增加总面数降低占比。小于10°用于统计，不新增所有面必须超过10°的要求。','',
'|输入|原父已有差面数|小于10°面数原版→候选|绝对差面面积mm²原版→候选|总面数原版→候选|候选六次差面数范围|',
'|---|---:|---:|---:|---:|---:|']
for row in summary['cases']:
    b,c=[row['methods'][m]['quality'] for m in ['baseline','candidate']]
    r=row['methods']['candidate']['repeat_quality_ranges']['below_10_faces']
    name=row['case'].removeprefix('未见')
    lines.append(f"|{name}|{row['input_parent_quality']['below_10_faces']}|{b['below_10_faces']}→{c['below_10_faces']}|{b['below_10_area_mm2']:.9g}→{c['below_10_area_mm2']:.9g}|{b['faces']}→{c['faces']}|{r['min']}—{r['max']}|")
lines += ['',
'两孔1781→27/25，差面数量分别减少约98.48%和98.60%，绝对差面面积也下降。薄壁50→0、窄缝42→0。普通切口60→41、55→29、54→45，CT首刀796→768、旧末刀634→568，收益有限；不由规则孔模型推断所有真实曲面都大幅改善。CT两份父输入本来已有607/471张差面，不能把全部输出差面归为本次布尔新产生。','',
'## 3. 完整速度分布，待统计后确定标准','',
'用户已明确“先看完整统计，再定速度标准”。当前不设固定毫秒、倍数或覆盖率验收值；215号此前“未保证速度”的表述对应当时判断，现以实际分布和失败记录供用户确定标准。每格为中位/P95/最大，单位毫秒，P95是六次样本的经验分位数。','',
'|输入|原版内核中位/P95/最大ms|候选内核中位/P95/最大ms|候选/原版中位倍率|',
'|---|---:|---:|---:|']
for row in summary['cases']:
    b,c=[row['methods'][m]['boolean_timing'] for m in ['baseline','candidate']]
    triple=lambda t:f"{t['median_ms']:.3f}/{t['p95_ms']:.3f}/{t['max_ms']:.3f}"
    lines.append(f"|{row['case'].removeprefix('未见')}|{triple(b)}|{triple(c)}|{row['boolean_median_ratio']:.3f}|")
lines += ['',
'这些是内核生成时间，排除加载、保存、SSH、抽样和准确审计；359号另保存六次进程墙钟分布。正式调用关闭区域轨迹，原版与候选同输入、同配置、交错测量，限制四个可用逻辑CPU。共享实例的跨轮快慢变化不能直接归因于某次改动，未作GPU加速结论。输出规模见上表，两孔大量增面也是实际成本。','',
'失败不能从速度报告删除：第十七轮原生连续第二刀实际30秒研究超时，候选无输出，随后14事件受阻；它不计成某个有限的内核耗时。第十九轮第四刀是约1.095秒进程墙钟后的自然断言失败，返回码1，绝不是30秒超时，也不是成功的1.095秒样本。研究运行30秒上限仅防止失控调用，不是用户速度标准。','',
'## 4. 保存几何和准确有效分母','',
f"全部182张实际重复保存对象均运行同一CGAL EPECK静态准确检查器：候选{audits['totals']['candidate']['embedded_closed']}/91，原版{audits['totals']['baseline']['embedded_closed']}/91准确嵌入且闭合。原版CT旧末刀七张各8自交配对，原版原第二刀负例七张各2配对；拒绝结果不抹去。候选原第二刀七次全部通过，这比仅检查首份更强，但仍限这些保存对象。",'',
'双向各8192面积样本及全部顶点探针见359号，保留距离分位数及0.01/0.05/0.1/0.15/0.2毫米覆盖比例。没有新增固定0.1毫米峰值要求或固定覆盖比例。原版拒绝网格的表面距离比较只是离散输出比较，不作为有效独立真值；静态准确检查和有限距离样本都不是一般连续几何证书。','',
'## 5. 原生连续反馈与修复经过','',
'当前真实十六刀从原初态重跑，不拼接任何旧帧：3发布、1拒绝、12受阻，保留完整16事件分母。17份初态/工具预审通过，已发布前三刀的实际父链、保存摘要、准确嵌入和同父输出质量复算通过350号。原版每刀使用同一个候选父输入，是同父控制，不能称独立原版连续路线。第四刀原版返回了网格，但该保存对象准确嵌入失败；候选自然断言失败，无输出。','',
'早期第二刀有约2.221e-15毫米新边。单边外部诊断收缩后2自交→0，285/286号只作为定位，不能冒充原生实现。第十七轮原生单轮收缩的84份候选保存仅80有效，失败四份都在同第二刀，附加轨迹有时有效，证明单看首份或一次成功不足。第十八轮隔离分组后仍失败。334号显示残余极短边仍满足流形链接，并全为新点，支持同轮一环互斥跳过的诊断；第十九轮保留单边约束、跨轮复查后，当前13例91/91全部准确通过，连续第二、三刀也通过。','',
'第四刀实际错误为Geogram `CDT_2d.cpp:610` 的`!Q.empty()`断言。原运行库addr2line将实际栈定位为`GEO::CoplanarFacets::triangulate()`，由`simplify_coplanar_facets(double)`并行区域调用触发。它属于准确共面区域三角化，不是Triangle细化失败；Release没有额外源码行信息，不编造缺失堆栈。368号保存真实第四刀输入、失败日志、同父原版输出和审计、实际库记录与三份源码。','',
'## 6. 证据、复现与下一步','',
'全部入口在`实验结果/20261006_Geogram内核质量生成`：336源码清单、337/338构建入口、341实际构建；352输入清单、353/354交错运行、357全部保存归档、358/359全部质量几何速度复算；360/361/364全部182准确复审；343/344/345原生十六刀反馈，348原始输出，349/350父链复算；367/368第四刀复用资产。','',
'真实远端目录`/tmp/geogram_native_quality_20261006_20`，原生调用`candidate parent.obj tool.obj output.obj`。原版安装、历史源码、前版本失败账本均保持；这些入口有不可覆盖检查，重现需新目录，不直接覆盖旧证据。既有Geogram和准确检查器依赖仍需原环境，未声明独立可移植包。GPU实例保持开启。','',
'下一步先用冻结第四刀父输入定位共面区域的约束退化，验证是否需要在准确共面再生成之前处理合法机器尺度新边；只作同源隔离验证，不能直接继续被拒绝链。新机制若改变，须从原初态重跑完整16事件并重新作全部同源回归，之后再冻结新独立输入评价。当前质量统计有真实明显改善，完整连续流程和最终交付仍未完成。','']
report.write_text('\n'.join(lines),'utf8')
root_doc=project/'研究内容1-创新点.md'
backup=here/'366-十三输入结果写入前创新点文档原字节.md';assert not backup.exists()
backup.write_bytes(root_doc.read_bytes())
note=f'''> **Geogram原生完整统计（216号）**：{now}（北京时间）。第十九轮十三开发输入182原生输出质量复算及准确复审完整：候选91/91、原版77/91；两孔1781→27/25，薄壁50→0、窄缝42→0，CT和普通切口收益有限。按用户要求先报中位、P95、最大及规模，不新增速度验收门槛。真实原生十六刀3发布、第四刀准确共面CDT自然断言、12受阻；第四刀不是超时。整体目标继续。详见[216号完整统计](初步实验/Geogram与PaMO组合验证/{report.name})。
>
> **生成时间**：{now}（北京时间）；**修改时间及修改内容**：{now}（北京时间），追加全部重复准确核查、速度分布及连续负例；**文档概述**：原生生成质量改善与连续剩余故障；**索引目录**：当前版本、完整质量速度、有效分母、连续失败及复用资产。

'''
root_doc.write_text(note+backup.read_text('utf8'),'utf8')
print(str(report));print('candidate_saved_objects',audits['totals']['candidate'])
