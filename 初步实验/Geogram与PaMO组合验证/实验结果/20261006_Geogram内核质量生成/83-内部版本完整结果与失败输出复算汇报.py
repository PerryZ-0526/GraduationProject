"""独立复算已失败批次的所有成功输出，汇报可用内部版本及真实负结果。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast
import hashlib
import json
import re
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
detector=here/'04-原版生成阶段同输入基线.py'
function=next(n for n in ast.parse(detector.read_text('utf8')).body if isinstance(n,ast.FunctionDef) and n.name=='quality')
scope={'np':np,'trimesh':trimesh}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(detector),'exec'),scope)
quality=scope['quality']
third_path=here/'57-第三轮原生十一同输入质量几何与速度复算.json'
third=json.loads(third_path.read_text('utf8'))
assert third['status']=='completed_all_154_saved_quality_recomputations_and_eleven_geometry_timing_pairs'
third_folder=here/'第三轮原生全部重复与诊断输出'
third_record_path=third_folder/'01-原生十一同输入交错质量速度记录.json'
third_record=json.loads(third_record_path.read_text('utf8'))
fifth_folder=here/'第五轮原生全部重复与诊断输出'
fifth_record_path=fifth_folder/'01-原生十一同输入交错质量速度记录.json'
fifth=json.loads(fifth_record_path.read_text('utf8'))
assert fifth['status']=='failed_actual_native_paired_development'
output=here/'84-内部顺序修订与共边负例完整复算汇总.json';assert not output.exists()
result={'生成时间':now(),'修改时间及修改内容':'第三轮完整复核及第五轮已失败批次所有成功输出复算',
        '文档概述':'完整第三轮与失败第五轮分开；均为开发输入；目标未达成',
        '索引目录':['fifth_actual_attempts','fifth_successful_saved_quality','third_additional_audits'],
        'status':'running','goal_achieved':False,'third_summary_sha256':sha(third_path),
        'third_record_sha256':sha(third_record_path),'fifth_record_sha256':sha(fifth_record_path),
        'fifth_actual_attempts':len(fifth['rows']),'fifth_successful_saved_quality':[],
        'third_additional_audits':[],'fifth_first_native_audits':[],'fifth_case_summaries':[]}
def save():
    """进度按已完成复算保存，不把失败整轮计为通过。"""
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
save()
for row in fifth['rows']:
    if row['returncode']!=0: continue
    p=fifth_folder/f"{row['case_index']:02d}"/Path(row['mesh_path']).name
    assert sha(p)==row['mesh_sha256']
    q=quality(p);assert q['faces']==row['native_timing']['faces']
    result['fifth_successful_saved_quality'].append({'case_index':row['case_index'],'method':row['method'],
        'repeat':row['repeat'],'mesh_sha256':sha(p),'quality':q})
for item in fifth['native_audits']:
    p=fifth_folder/f"{item['case_index']:02d}"/Path(item['audit_path']).name
    assert sha(p)==item['audit_sha256']
    audit=json.loads(p.read_text('utf8'));native=json.loads(audit['stdout']) if audit['returncode']==0 else None
    result['fifth_first_native_audits'].append({'case_index':item['case_index'],'method':item['method'],'native':native})
for item in third_record['generation_traces']:
    i=item['case_index'];p=third_folder/f'{i:02d}'/'candidate_trace_native_audit.json'
    assert sha(p)==item['audit_sha256']
    mesh=third_folder/f'{i:02d}'/'candidate_trace.obj';assert sha(mesh)==item['mesh_sha256']
    audit=json.loads(p.read_text('utf8'))
    result['third_additional_audits'].append({'case_index':i,'scope':'separate_trace_saved_output',
        'native':json.loads(audit['stdout']) if audit['returncode']==0 else None,'quality':quality(mesh)})
for item in third_record['raw_stage_audits']:
    i=item['case_index'];p=third_folder/f'{i:02d}'/'candidate_no_simplify_native_audit.json'
    assert sha(p)==item['audit_sha256']
    mesh=third_folder/f'{i:02d}'/'candidate_no_simplify.obj';assert sha(mesh)==item['mesh_sha256']
    audit=json.loads(p.read_text('utf8'))
    result['third_additional_audits'].append({'case_index':i,'scope':'no_coplanar_simplification',
        'native':json.loads(audit['stdout']) if audit['returncode']==0 else None,'quality':quality(mesh)})
for i in range(10):
    entries=[r for r in fifth['rows'] if r['case_index']==i and r['repeat']>=0]
    assert len(entries)==12
    methods={}
    for method in ['baseline','candidate']:
        rows=[r for r in entries if r['method']==method]
        qs=[r['quality'] for r in result['fifth_successful_saved_quality'] if r['case_index']==i and r['method']==method and r['repeat']>=0]
        methods[method]={'bad_min':min(q['below_10_faces'] for q in qs),'bad_max':max(q['below_10_faces'] for q in qs),
            'bad_area_min':min(q['below_10_area_mm2'] for q in qs),'bad_area_max':max(q['below_10_area_mm2'] for q in qs),
            'boolean_median_ms':float(np.median([r['native_timing']['boolean_ms'] for r in rows]))}
    result['fifth_case_summaries'].append({'index':i,'methods':methods})
assert len(result['fifth_successful_saved_quality'])==141
assert len(result['fifth_first_native_audits'])==20 and len(result['third_additional_audits'])==13
result.update(status='completed_all_141_successful_fifth_outputs_and_third_additional_saved_audits',finished_beijing=now())
save()
parent=here.parents[1]
numbers=[int(m.group(1)) for p in parent.glob('*.md') if (m:=re.match(r'^(\d+)-',p.name))]
number=max(numbers)+1
report=parent/f'{number:02d}-Geogram内部生成索引修订与共享边细化负例.md';assert not report.exists()
stamp=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日 %H:%M:%S（北京时间）')
table=[]
for case in third['cases']:
    b,c=[case['methods'][m] for m in ['baseline','candidate']]
    table.append(f"|{case['index']}|{b['quality']['below_10_faces']}→{c['quality']['below_10_faces']}|{c['repeat_quality_ranges']['below_10_faces']['min']}—{c['repeat_quality_ranges']['below_10_faces']['max']}|{b['boolean_timing']['median_ms']:.3f}→{c['boolean_timing']['median_ms']:.3f}|{c['first_output_embedded_closed']}|")
candidate_ok=sum(c['methods']['candidate']['first_output_embedded_closed'] for c in third['cases'])
assert candidate_ok==11
text=f'''# Geogram内部生成索引修订与共享边细化负例

生成时间：{stamp}

修改时间及修改内容：{stamp}，首次记录内部顺序修订的完整十一输入评价、共边细化实际失败和所有成功保存输出复算。

文档概述：用户要求Geogram生成时就减少细长面并保住速度。第三轮是直接修改原生生成内核的可运行候选；第五轮边界补点没有达到目标，不交付为最佳版本。总体目标仍在进行。

索引目录：1.版本身份；2.第三轮完整结果；3.第五轮负结果；4.结论与下一步。

## 1. 版本身份与实际修改

206、212号是本任务早期的外部维护产物，不是官方Geogram原版。213号起才实际修改Geogram内部区域三角化。第三轮在首轮内部细化之上，将零长度边收缩放到准确点操作完成后，重建分类压缩后的准确点编号，并区分已删除点；所有修改仍在原生布尔入口内，无Python重铺或PaMO。两份双精度坐标完全相同的顶点，仅在闭合流形边链接条件成立时合并，保留点坐标不移动。

第三轮实际编译和评价已结束，49、53、57号分别绑定源码、执行和完整复算。第二轮已编译但未用于正式质量结论；其提前收缩及索引风险通过显式第三轮修订解决，旧源码保持。各轮只读复用逐字节一致的官方原版基线，未把本次旧研究候选当作原版。

## 2. 第三轮十一同输入完整结果

输入序号同18号固定清单：0—2普通切口，3—4薄壁，5—6窄缝，7—8贯通孔，9、10真实CT首刀及旧路线末刀的实际切削前父输入。均为已见开发输入。每方法预热一次、重复六次，全部154份保存输出独立复算；原版和候选首份各十一份作准确静态嵌入检查。

|输入序号|首份小于10度面数原版→候选|候选六次面数范围|同轮内核中位毫秒原版→候选|候选首份准确嵌入|
|---|---:|---:|---:|---|
'''+ '\n'.join(table)+'''

两薄壁绝对差面数量50→8，减少84%；普通切口仍是部分改善。窄缝42→42，孔总体改善很小，不能据局部好例称整体目标完成。CT末刀重复差面计数有小幅变化，完整范围保留，不挑最好一次；也不将不同轮原版计数漂移当作候选收益。

第三轮候选首份准确闭合嵌入11/11，原版10/11。另行带轨迹生成的十一保存输出及两份禁共面简化CT保存输出，13/13也通过准确静态检查；不把这些检查冒称为全部154重复逐一EPECK检查，更不称连续切削验证。末刀禁简化输出由原版两张零面积面和八个自交配对，变为零退化、零自交配对、闭合嵌入；这个结果证明特定双精度零边处理有效，不保证任意退化输入。

57号保留双向8192面积样本、全部顶点探针、多个距离覆盖比例及分位数。零位移收缩不等于连续表面误差证书；未新增固定0.1毫米峰值或通过比例要求。共享实例中部分原版和候选计时有明显波动，六次全部范围保留，不据单例快于原版宣称普遍加速或实时速度保证。

逐区域轨迹显示：窄缝只补内部点的候选为42→7，但绝对坏面面积约0.0504221→0.221207/0.218581平方毫米，被数量和面积检查拒绝。不是生成器没有提出候选，也不是单纯达到64点预算；这两例实际新增49点。

## 3. 第五轮共边细化负结果

第四轮试图允许边界补点，准确插值回原约束线，并同步相邻面；首次准备的命名空间个数断言失败只留下空目录，恢复只允许空目录。实际编译又因GEO单元素容器初始化列表失败，完整日志保留。第五轮显式修订容器初始化及两侧已分段边同步，实际编译通过后重新执行同十一输入，没有覆盖或拼接旧结果。

第五轮整批实际终态为失败：142次尝试，141份成功保存网格，CT末刀候选首次预热崩溃；不是154次完整评价。141份成功输出已全部独立复算，前十输入首份原版及候选的20份准确检查通过。完整原始记录、崩溃堆栈、141质量结果见84号。失败后两窄缝及CT另外单独诊断三次，不补写原142条账本。

共边插点会把部分邻面划成新的差面：普通00的暂定整体小角数60→91，薄壁50→300，CT首刀796→835，均被内核整体数量和面积检查回退。孔的两个首份候选1768/1767差面且准确嵌入通过，但不能用这些好例掩盖其他回退和末刀崩溃。

窄缝边界可补点后，区域候选42→8，但坏面面积仍约0.0934367/0.0939539平方毫米，大于原0.0504221，因此仍拒绝。实际新增39点，未达到64点上限，不支持直接归因为点数预算不足。单纯放开边界补点没有解决问题。

CT崩溃堆栈实际符号定位为Triangle的enqueuebadtriang→tallyfaces→enforcequality。源码队列用最短边平方长度的指数分桶；当前尚未捕获触发崩溃的具体key及区域输入，不能将坐标量化或零边当作已证完整根因。第三轮同源输入正常、第五轮该输入崩溃的事实保留。

## 4. 当前结论与后续依据

当前可运行、验证覆盖最完整的内部版本是第三轮；第五轮不能替换它。研究尚未满足普通切口、窄缝、孔和CT上普遍大幅减少细长面及速度目标。不能为了放行42→7而只看面数、忽略坏面面积，也不能把区域收益抵消邻面的代价后仍称成功。

下一项应优先捕获Triangle崩溃的实际输入和队列条件；质量上尝试仅对剩余大面积差面进行有界细化，并在共边同步后重新改善受影响邻面的三角化。必须保留原点与来源信息，继续整体数量、面积、准确嵌入及原生耗时对照；不能直接把所有边界补点的当前负结果扩展成最终交付。
'''
# 本报告只写已核对的孔计数，若实际保存值不同则生成前失败，不填猜测。
holes=[result['fifth_case_summaries'][i]['methods']['candidate']['bad_min'] for i in [7,8]]
text=text.replace('1768/1767差面',f'{holes[0]}/{holes[1]}差面')
report.write_text(text,'utf8')
root=here.parents[3]/'研究内容1-创新点.md'
backup=here/'85-内部版本进展汇报前研究内容备份.md';assert not backup.exists();backup.write_bytes(root.read_bytes())
header=f'> **Geogram内部生成进展（{number}号）**：{stamp}，第三轮十一同输入完整154份复算、候选首份11/11准确嵌入，另13/13轨迹和禁简化保存检查通过；薄壁50→8，窄缝仍42。第五轮142尝试、141保存后CT末刀崩溃，整批失败及所有成功输出复算保留，不替换第三轮。目标尚未达成，详见[本轮结果](初步实验/Geogram与PaMO组合验证/{report.name})。\n\n'
root.write_text(header+backup.read_text('utf8'),'utf8')
receipt={'生成时间':now(),'修改时间及修改内容':'汇报内部可运行候选及真实负例',
         '文档概述':'目标保持活动；未冒称成功交付','索引目录':['report'],
         'status':'completed_native_progress_and_failure_report_goal_not_achieved',
         'report':str(report),'report_sha256':sha(report),'summary_sha256':sha(output),
         'root_backup_sha256':sha(backup),'root_updated_sha256':sha(root)}
(here/'86-内部版本与负例进展汇报回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n','utf8')
print(str(report),flush=True)
print('第三轮完整，失败第五轮141成功保存输出已全部复算；目标未达成',flush=True)
