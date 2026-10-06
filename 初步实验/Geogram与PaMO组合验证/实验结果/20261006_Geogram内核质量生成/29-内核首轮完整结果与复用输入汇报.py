"""保存首轮内部算法真实收益及负结果，研究目标仍需后续生成改进和连续验证。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import shutil

here=Path(__file__).resolve().parent
directory=here.parents[1]
workspace=here.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
qp=here/'25-原生十一同输入质量几何与速度复算.json'
ip=here/'28-原生差面继存与重新生成来源核对.json'
mp=here/'18-原生十一同输入开发与速度运行前清单.json'
quality,inheritance,manifest=[json.loads(p.read_text('utf8')) for p in [qp,ip,mp]]
assert quality['status']=='completed_all_154_saved_quality_recomputations_and_eleven_geometry_timing_pairs'
assert inheritance['source_quality_sha256']==sha(qp) and len(quality['cases'])==11
controller=json.loads((here/'21-原生配对执行取回记录.json').read_text('utf8'))
assert controller['status']=='completed_native_paired_outputs_retrieved'
assert len(controller['only_three_generation_sources_differ'])==3
raw_path=here/'真实CT原版禁简化阶段定位/01-真实CT禁简化来源阶段记录.json'
raw=json.loads(raw_path.read_text('utf8'))
assert raw['status']=='completed_two_saved_raw_CT_stage_diagnoses'
number=max(int(m.group(1)) for p in directory.glob('*.md') if (m:=re.match(r'^(\d+)-',p.name)))+1
report=directory/f'{number:02d}-Geogram内部质量生成首轮同配置对照与速度结果.md'
stamp=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日 %H:%M:%S（北京时间）')
table=['|输入|原版→候选小角面|重新生成差面|面数原版→候选|内核中位毫秒原版→候选|首份准确嵌入|',
       '|---|---:|---:|---:|---:|---|']
for row,origin in zip(quality['cases'],inheritance['rows']):
    b,c=[row['methods'][x] for x in ['baseline','candidate']]
    before,after=[origin['methods'][x] for x in ['baseline','candidate']]
    table.append(f"|{row['case']}|{b['quality']['below_10_faces']}→{c['quality']['below_10_faces']}|"
                 f"{before['bad_regenerated_triangles']}→{after['bad_regenerated_triangles']}|"
                 f"{b['quality']['faces']}→{c['quality']['faces']}|"
                 f"{b['boolean_timing']['median_ms']:.3f}→{c['boolean_timing']['median_ms']:.3f}|"
                 f"{b['first_output_embedded_closed']} / {c['first_output_embedded_closed']}|")
valid=sum(r['methods']['candidate']['first_output_embedded_closed'] for r in quality['cases'])
improved=sum(r['bad_count_change']<0 for r in quality['cases'])
maximum=max(v['all_vertices_max_mm'] for r in quality['cases'] for v in r['geometry'].values())
ratios=[r['boolean_median_ratio'] for r in quality['cases']]
text=f'''# Geogram内部质量生成首轮同配置对照与速度结果

生成时间：{stamp}

修改时间及修改内容：{stamp}，首次记录实际Geogram源码改动、同配置双构建、十一开发输入全部重复、准确检查及速度负结果。

文档概述：已直接修改Geogram内部区域三角化，生成结果不接Python网格维护。部分模型大幅改善，窄缝及真实CT数值负例尚未解决；总体研究目标保持进行状态。

索引目录：1.实际实现；2.完整同输入结果；3.速度及几何；4.失败定位；5.复用与下一步。

## 1. 实际内部实现及基线

原版实际源码来自既有实例Geogram 1.10.2-rc构建目录，本地较新参考版本与其不同，未混用源码。两份隔离构建使用相同Release、Triangle支持和TBB链接配置，2300份源文件只有三份生成阶段文件不同；逐文件差异及实际库、执行器摘要保存在构建记录及控制器中。

候选在`mesh_boolean_operation`调用的共面区域生成内部工作：原准确CDT确定边界及孔洞；只对有差面的区域调用Triangle有界内部点细化；保持输入边界点及约束段，新增点准确提升到原支撑平面；小角数量与绝对坏面面积同时不恶化且至少一项改善才采用。并行提取结束后统一提交新点与三角形，避免共享网格扩容影响读者。

参数为`rpzq20YYS64Q`，每区域最多64个新增内部点。20度是生成目标，不能当作所有输出角度保证。没有额外调用Python局部重铺、PaMO或GPU。原作者目录、旧206/212源码及输出保持。

## 2. 十一开发输入完整实际结果

九份既有参数输入及两份真实CT原始布尔父输入，均已用于开发，不称新的未见评价。每方法每输入预热一次、重复六次，全部154份输出保存并独立复算质量；首份原版及候选各十一网格实际作EPECK静态嵌入检查。

{chr(10).join(table)}

十一输入中{improved}例小角绝对数量减少，两窄缝不变，无增加例。两薄壁总小角面50→8，减少84%；与输入完整三角形不相同的重新生成差面46→4，减少约91.3%。三普通切口总数量减少31.7%、47.3%、16.7%。两个孔的1728个原有差面完整继存，不能把总1781→1772称为大幅改善；重新生成差面53→44仅约17.0%。

“重新生成”按双精度坐标完整三角形与输入集合不同判定，也包含原背景面的重新划分，不自动代表纯切削因果。完整数量、坏面真实面积和面数分别报告，不用增加好面稀释比例。

本轮最小角使用atan2叉积与点积，非有限或非正面积另列；没有采用历史1e-12平方毫米有效面门槛。因此CT796/634等数值不能直接与206号另一有效面口径的283/430等相比。统计口径差异不等于算法退步或进步。

## 3. 实际速度与几何分布

原版和候选在同一机器、同一输入、相同四个逻辑处理器亲和性下交错执行。六次内核中位耗时倍率范围为{min(ratios):.3f}—{max(ratios):.3f}；单次范围和95%分位全部保存在25号JSON。小模型候选约11.7—109.4毫秒，两CT控制约748.6/676.7毫秒。某例略快不作为一般加速结论；约22%的中位代价及最大耗时真实保留，尚无任意负载或实时速度保证。

这些计时为原生布尔生成调用，加载和保存单列；另有独立进程完整耗时。不含SSH传输、研究评价、精确检查、GUI显示或仿真其他模块，不能与206号106秒维护管线直接作加速比。

十一对首份同输入输出的双向8192面积样本及全部顶点最近距离已计算，全部顶点探针峰值约{maximum:.12g}毫米，分位数和0.01/0.05/0.1/0.15/0.2毫米覆盖率完整保留。当前结果支持保存几何几乎相同，抽样与顶点探针不构成连续表面距离证书。没有新设0.1毫米峰值门槛或通过比例。

首份候选准确闭合嵌入{valid}/11；其余六次重复全部质量复算，不冒称每次重复都另作完整精确检查。CT末刀原版和候选均有两个零面积面，首份都未通过准确嵌入，闭合或较小距离不能替代该失败。

## 4. 实际失败与来源定位

首次基线在十八输出完成后因误用CT维护源输入字段退出1，十八输出、原running记录及05号实际终止说明全部保留；正式十一对照修正为真实切削前父输入，不拼接已切削维护源。首次编译启动缺少python3、首次原版链接缺少TBB、恢复脚本参数名冲突分别真实保留；实际第三次同配置构建双方完整通过。这些环境和脚本修复没有改候选生成机制。

两份CT相同父输入另实际执行原版禁共面简化。首刀原始交线阶段无零面积面且准确嵌入通过；末刀原始交线阶段已含两个零面积面和八个自交配对，准确嵌入未通过。因此该负例早于新增区域细化，不能靠增加内部点消除，也不能计为成功输出。

## 5. 复用输入与下一步

本目录保存三份候选内部源码、原版对应源文件、构建及失败记录、完整重复输出与审计、来源核对及固定输入清单。十一原始父输入和工具另完整保存到可复用原生内核开发输入目录，并逐文件核对摘要；运行依赖仍为实例既有Geogram依赖和CGAL检查器，不声明独立可移植安装包。

用户要求的最终目标仍是Geogram直接输出显著更少细长面并保住速度。当前只有部分模型达成大幅质量改善；窄缝、孔和CT仍缺少足够收益，CT数值合法性也需解决。下一轮应定位剩余约束边界导致的差面，以及准确交点转为双精度时的零面生成，再改内部机制；修订后需新版本及完整同输入、连续切削和速度验证。不得将本轮十一静态开发或薄壁收益替代整体目标完成。
'''
asset=here/'可复用原生内核开发输入';asset.mkdir()
input_rows=[]
for i,case in enumerate(manifest['cases']):
    row={'id':case['id'],'files':{}}
    for key in ['parent','tool']:
        source=Path(case[key]);assert sha(source)==case[key+'_sha256']
        destination=asset/f'{i:02d}-{case["id"]}-{key}.obj'
        shutil.copy2(source,destination);assert sha(destination)==case[key+'_sha256']
        row['files'][key]={'path':destination.name,'sha256':sha(destination),'original_path':str(source)}
    input_rows.append(row)
(asset/'01-复用原生开发输入清单.json').write_text(json.dumps({'生成时间':stamp,'修改时间及修改内容':'首次保存十一布尔父输入和工具',
    '文档概述':'全部已见开发输入；摘要与实际配对一致','索引目录':['rows'],'rows':input_rows},ensure_ascii=False,indent=2)+'\n','utf8')
report.write_text(text,'utf8')
root=workspace/'研究内容1-创新点.md'
original=root.read_bytes()
(here/'30-内部质量生成汇报更新前研究内容备份.md').write_bytes(original)
prefix=f'''> **本次进展记录生成时间**：{stamp}
> **修改时间及修改内容**：{stamp}，追加Geogram内部生成真实改动及首轮同配置质量速度结果。
> **文档概述**：三份内部生成源码已改，十一同输入154输出完整；部分收益显著，目标仍继续。
> **索引目录**：实际内核身份；质量及成本；CT来源失败；后续验证。

- 本轮直接改Geogram内部区域三角化，不接Python维护；两薄壁50→8，普通切口60→41、55→29、54→45。
- 窄缝不变，两孔原有1728差面继存；候选首份准确检查10/11，末刀原版及候选的零面积负例保留。
- 六次交错计时与全部154输出质量已复算，内核中位倍率约{min(ratios):.3f}—{max(ratios):.3f}，没有整体速度或算法成功保证。
- 完整证据见[{number:02d}号内核首轮结果]({report.as_posix()})；研究目标继续，不能据单模型或静态开发宣布完成。

'''
root.write_bytes(prefix.encode('utf8')+original)
assert root.read_bytes().endswith(original)
(here/'31-内核首轮完整汇报与复用核对回执.json').write_text(json.dumps({'生成时间':stamp,
    '修改时间及修改内容':'首次完成本轮内部源码和实际配对结果汇报','文档概述':'目标仍进行，不宣称最终成功',
    '索引目录':['report','evidence'],'status':'completed_first_native_kernel_development_report_goal_not_achieved',
    'report':str(report),'report_sha256':sha(report),'quality_sha256':sha(qp),'inheritance_sha256':sha(ip),
    'raw_CT_diagnosis_sha256':sha(raw_path),'saved_repeat_outputs':154,'source_files_changed':3,
    'first_candidate_native_passed':valid,'cases':11,'reusable_input_files':22},ensure_ascii=False,indent=2)+'\n','utf8')
print('首轮内部算法结果已保存',report.name,flush=True)
