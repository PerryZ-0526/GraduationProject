"""完整统计生成中文报告，旧记录和根文档正文保留。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

here=Path(__file__).resolve().parent
parent=here.parent.parent
new=json.loads((here/'582-新边拒绝固定方法第二批十六新参数完整复算.json').read_text('utf8'))
speed=json.loads((here/'649-免重复判定十六已见三方法完整统计.json').read_text('utf8'))
ct=json.loads((here/'641-免重复判定原生CT十六刀保存联合复算.json').read_text('utf8'))
freeze=json.loads((here/'651-免重复判定当前原生候选完整证据封存.json').read_text('utf8'))
assert speed['status'].startswith('completed_all_336') and new['status'].startswith('completed_all_224')
assert ct['totals']['accepted']==16
now=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日 %H:%M:%S')
report=parent/'219-Geogram原生新参数完整统计与免重复判定提速结果.md';assert not report.exists()
prefix='实验结果/20261006_Geogram内核质量生成/'
def link(name):
    """本报告内使用真实本地相对链接，用户主答复仍用绝对路径。"""
    return f'[{name}]({prefix}{name})'
def t(value):
    """完整列最小、中位、P95和最大，不截去尖峰。"""
    return ' / '.join(f'{value[k]:.3f}' for k in ['min_ms','median_ms','p95_ms','max_ms'])
ratios=[c['candidate_previous_median_ratio'] for c in speed['cases']]
slow=[c['candidate_baseline_median_ratio'] for c in speed['cases']]
lines=['# Geogram原生新参数完整统计与免重复判定提速结果','',
    f'**生成时间**：{now}（北京时间）',f'**修改时间及修改内容**：{now}（北京时间），首次汇总固定方法新参数完整终态、失败提速方案、阶段计时和当前免重复判定实际成果。',
    '**文档概述**：原生API返回时已完成质量生成；固定569方法独立新参数224次均返回并精确有效。当前免重复判定副本336次三方法与连续16刀均有效，质量数量保持，速度有所改善；部分输入改善有限，整体目标未宣布完成。',
    '**索引目录**：1. 结论与版本；2. 固定方法独立新参数；3. 当前三方法完整速度与规模；4. 连续反馈；5. 失败尝试与阶段诊断；6. 源码及复现。','',
    '## 1. 结论与版本','',
    '当前效果最好的可继续使用原生副本是第二十四轮免重复判定版：569号新边拒绝规则、准确共面CDT、内部及一致共享边质量生成均保持，只跳过已经为真的接缝顶点保留判定。keep标记只从false变true，跳过时仍推进前驱，避免重复复制准确坐标和精确计算。新方法真实源码及编译库见651号封存。',
    '569号固定方法在生成新参数前已封存：16输入×2方法×7调用=224次全部返回，原版及候选各112/112保存对象精确通过。新参数来自普通切口、旋转薄壁/窄缝/通孔及已有CT的新位置和工具，CT不是新患者。',
    '当前免重复判定版是在新参数已打开后修改的开发版，不能继承569方法的独立评价身份。三方法实际开发比较为16输入×3方法×7调用=336次，原版、569及当前版各112/112精确通过，所有失败分母和全部重复均保留。',
    f'当前各输入中位耗时比同次569版减少约{100*(1-max(ratios)):.2f}%—{100*(1-min(ratios)):.2f}%；相对原版仍为约{min(slow):.3f}—{max(slow):.3f}倍。通孔细长面数量减少约94%—97%，部分薄壁/窄缝只减少1个，CT约4%—6%，不称所有类型大幅改善。用户要求先看完整统计再定速度标准，本报告不设固定延迟、误差或覆盖率验收门槛。','',
    '## 2. 固定方法独立新参数','',
    '输入固定种子2026100704，随机执行计划2026100705。所有32份初态/工具在首次生成前精确检查，三份生成源码、库、二进制与569封存绑定。每方法一次预热、六次正式调用。以下为首个正式输出与六次原生内部耗时；面积是细长面绝对面积，避免仅靠新增面数稀释比例。','',
    '|输入|小于10°面数 原版→569|细长面面积 原版→569 mm²|输出面数 原版→569|原版 最小/中位/P95/最大 ms|569 最小/中位/P95/最大 ms|',
    '|---|---:|---:|---:|---|---|']
for c in new['cases']:
    b=c['methods']['baseline'];a=c['methods']['candidate'];bq=b['quality'];aq=a['quality']
    lines.append(f"|{c['index']:02d} {c['case']}|{bq['below_10_faces']}→{aq['below_10_faces']}|{bq['below_10_area_mm2']:.9g}→{aq['below_10_area_mm2']:.9g}|{bq['faces']}→{aq['faces']}|{t(b['boolean_timing'])}|{t(a['boolean_timing'])}|")
lines+=['',f"全部重复质量范围、进程耗时及有限双向几何分布见{link('582-新边拒绝固定方法第二批十六新参数完整复算.json')}，全部224保存对象准确复审见{link('585-新边拒绝第二批新参数全部输出准确复审实际取回记录.json')}。若该复审链接文件名与现场不符，以587号完整ZIP及其实际记录为准。",
    '16例首份细长面绝对数量及面积均下降，但三组薄壁/窄缝数量仅下降约1%，不能把16/16方向正确写成16/16大幅改善。几何结果为有限面积抽样和全部顶点探针，不是连续距离证书。','',
    '## 3. 当前三方法完整速度与规模','',
    '三方法在相同输入按固定种子2026100706交错，一次预热、六次正式调用；所有336实际输出逐份精确审计。该组是已见开发回归。时间为原生布尔全过程，包括内核质量生成，排除加载保存、网络与外部精确审计。CPU限制四个逻辑处理器，未声称GPU加速或固定实时保证。','',
    '|输入|原版 最小/中位/P95/最大 ms|569 最小/中位/P95/最大 ms|当前 最小/中位/P95/最大 ms|当前输出面数|当前/569中位|当前/原版中位|',
    '|---|---|---|---|---:|---:|---:|']
for c in speed['cases']:
    m=c['methods'];lines.append(f"|{c['index']:02d} {c['case']}|{t(m['baseline']['boolean_timing'])}|{t(m['previous']['boolean_timing'])}|{t(m['candidate']['boolean_timing'])}|{m['candidate']['first_quality']['faces']}|{c['candidate_previous_median_ratio']:.3f}|{c['candidate_baseline_median_ratio']:.3f}|")
lines+=['','当前所有输入细长面数量与同次569输出一致，面积的机器精度浮点求和差异和所有重复范围保留在649号。未修改质量规则或减少输出面数来提速；通孔输出约2.1万—2.7万面，仍需计入后续操作成本。','',
    '|输入|原版含加载保存进程 最小/中位/P95/最大 ms|569含加载保存进程 最小/中位/P95/最大 ms|当前含加载保存进程 最小/中位/P95/最大 ms|',
    '|---|---|---|---|']
for c in speed['cases']:
    m=c['methods'];lines.append(f"|{c['index']:02d} {c['case']}|{t(m['baseline']['process_timing_all_measured'])}|{t(m['previous']['process_timing_all_measured'])}|{t(m['candidate']['process_timing_all_measured'])}|")
lines+=['',f"全部336逐对象质量、准确审计、输入摘要和双向有限几何检查：{link('649-免重复判定十六已见三方法完整统计.json')}。当前通孔433.752毫秒、CT1126.132毫秒尖峰均计入，六次样本的P95只是这次样本分位数。","",
    '## 4. 连续反馈','',
    '当前副本从原CT初态与原16工具完整重跑，16/16发布，零拒绝、零阻断；保存网格、原工具摘要、逐刀真实父链及同候选父输入的原版输出均复算。每刀只测一次，以下不是六次重复速度分布；原版控制使用候选父输入，不是原版独立反馈路线。','',
    '|实际事件|最小 ms|中位 ms|P95 ms|最大 ms|完整分母|','|---|---:|---:|---:|---:|---:|']
for m,label in [('baseline','原版同父控制'),('candidate','当前原生反馈')]:
    value=ct['totals']['timing_per_actual_event'][m];lines.append(f"|{label}|{value['min_ms']:.3f}|{value['median_ms']:.3f}|{value['p95_ms']:.3f}|{value['max_ms']:.3f}|16|")
lines+=['',f"原生连续证据见{link('641-免重复判定原生CT十六刀保存联合复算.json')}及637号原ZIP。原569版十五刀磁盘中断与仅恢复未执行末刀、独立原版第三刀拒绝的旧事实仍见218/217号，不覆盖旧账本。","",
    '## 5. 失败尝试与阶段诊断','',
    '第二十三轮尝试保留好区所有顶点、跳过其重建，完整16刀仅3发布，第4刀精确拒绝，后12受阻；604号保存复算及602号原ZIP保留。该版不作为交付候选，也不以成功前缀计算完整路线速度。',
    '独立阶段计时副本仅加chrono与诊断打印，四类输入20次全部静态精确通过。CT三个诊断正式调用的原生中位约1041.565毫秒，共面阶段约691.666毫秒；区域发现和接缝锚定在深度0/1分别约237.720/232.733毫秒，Triangle本身合计中位约1.331毫秒。递归时间已包含在父阶段，不重复相加；各项中位也不能相加当成一次调用。',
    '由此先优化重复精确接缝判定，而未减少质量预算。诊断副本不混入正式统计。614客户端status残留running但returncode=0，618号按实际ZIP终态20条记录完成状态核对，原614记录不回写。',
    f"阶段证据：{link('618-稳定原生四类阶段诊断完整统计.json')}；小样本先导20调用见639号，孔的单次参照尖峰451.555毫秒不据此宣称提速一半，以336交错数据为正式比较。","",
    '## 6. 源码及复现','',
    f"当前代码：{link('651-免重复判定当前原生候选完整证据封存.json')}，源码在免重复判定当前原生候选封存目录，五文件摘要及与569版本的唯一源码差异已记录；实际原生目录/tmp/geogram_native_quality_20261007_32，原版基线只读复用02号。", 
    '使用651绑定的实际候选执行`candidate parent.obj tool.obj output.obj`即可返回内核质量结果，NATIVE_RESULT里的boolean_ms为上述内部耗时。编译脚本仍依赖02号完整冻结源码与原版，五文件封存不是独立跨环境安装包。实际CMake为Release、Linux64-gcc-dynamic、Triangle开启、graphics/Tetgen/HLBFGS/legacy/Lua关闭、TBB选项关闭而GCC链接-ltbb，参数和三份实际源码详见625号。',
    '569独立评价与当前开发回归分别保存；当前版本尚无新未见输入评价，不宣称任意输入成功、所有骨面质量大幅改善或速度已达用户标准。GPU实例保持开启，整体目标继续。','']
# 准确复审文件名由现场确定，不能留一个可能失效的链接。
audit=next(here.glob('585-*.json')).name
text='\n'.join(lines).replace('585-新边拒绝第二批新参数全部输出准确复审实际取回记录.json',audit)
text=text.replace('。若该复审链接文件名与现场不符，以587号完整ZIP及其实际记录为准。','。')
report.write_text(text,'utf8')
root=next(p for p in here.parents if (p/'研究内容1-创新点.md').is_file())/'研究内容1-创新点.md'
backup=here/'653-追加219号前研究内容创新点原字节备份.md';assert not backup.exists();shutil.copy2(root,backup)
entry=f'> **Geogram原生完整统计与当前提速（219号）**：{now}（北京时间）。569封存后第二批新参数224/224返回、双方112/112保存精确通过。当前免重复判定版16已见输入三方法336/336准确通过，较569同输入中位提速约3%—21%，细长面数量保持；完整CT16/16父链与保存复算通过。通孔数量减少约94%—97%，部分薄壁/窄缝仅1个，CT收益有限；相对原版仍约1.04—3.23倍，先列完整分布再定速度标准。651封存，整体目标继续。详见[219号完整统计](初步实验/Geogram与PaMO组合验证/{report.name})。\n>\n> **生成时间**：{now}（北京时间）；**修改时间及修改内容**：{now}（北京时间），追加新参数终态、阶段诊断及免重复判定完整质量速度统计；**文档概述**：原生当前候选成果与剩余边界；**索引目录**：固定方法独立评价、开发提速、连续反馈、源码封存。\n\n'
root.write_text(entry+root.read_text('utf8'),'utf8')
print('reported_219_and_preserved_root_backup')
