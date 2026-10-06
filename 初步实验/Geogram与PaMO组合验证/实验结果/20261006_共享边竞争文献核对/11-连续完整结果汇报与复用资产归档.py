"""六项实际终态复审通过后汇总完整结果，归档全部候选与未采用输出，不隐去退步帧。"""
from pathlib import Path
from fractions import Fraction
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import hashlib
import json
import re
import shutil
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from matplotlib.font_manager import FontProperties


def digest(path):
    """用分块读取绑定归档字节，避免大型阶段文件占满内存。"""
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def save(path, value):
    """所有生成对象显式保存为中文可读文本。"""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', 'utf8')


here = Path(__file__).parent
workspace = Path.cwd()
evidence = Path('D:/GraduationProject_切削排斥证据')
study = evidence/'20261006_Geogram共享边竞争生成真实CT连续验证'
coordinator_path = here/'04-连续终态六项复审顺序执行记录.json'
coordinator = json.loads(coordinator_path.read_text('utf8'))
assert coordinator['status'] == 'completed_all_six_bound_terminal_audits' and len(coordinator['rows']) == 6
rp = study/'真实CT完整父反馈结果/01-真实CT十六刀完整父反馈记录.json'
assert digest(rp) == coordinator['source_record_sha256']
record = json.loads(rp.read_text('utf8'))
assert record['status'] == 'completed_with_recorded_outcomes' and len(record['routes'][0]['events']) == 16
mp = study/'43-共享边竞争生成真实CT十六刀冻结清单.json'
manifest = json.loads(mp.read_text('utf8'))
assert record['manifest_sha256'] == digest(mp)
baseline_path = Path(manifest['baseline_reference'])
assert digest(baseline_path) == manifest['baseline_record_sha256']
baseline = json.loads(baseline_path.read_text('utf8'))
baseline_published = sum(e['status'] == 'published' for e in baseline['routes'][0]['events'])
batch_seconds = {name: (datetime.fromisoformat(value['finished_beijing'])-datetime.fromisoformat(value['生成时间'])).total_seconds()
    for name, value in [('new', record), ('baseline', baseline)]}
diagnosis_path = here/'16-第十五刀保存拒绝面几何来源诊断.json'
equivalence_path = here/'18-拒绝初始面与已接受翻边对象一致性复核.json'
diagnosis, equivalence = [json.loads(p.read_text('utf8')) for p in (diagnosis_path, equivalence_path)]
assert diagnosis['source_record_sha256'] == equivalence['source_record_sha256'] == digest(rp)
assert equivalence['diagnosis_sha256'] == digest(diagnosis_path)
assert equivalence['status'] == 'completed_rejected_initial_equals_exactly_checked_accepted_flip_object'
assert equivalence['vertices_faces_labels_equal'] and equivalence['prior_native_embedded_closed']
assert not diagnosis['local_competing_strategy_executed_on_rejected_event']
refusal_face = diagnosis['rows'][0]
for path, expected in manifest['modules'].items():
    assert digest(Path(path)) == expected
audits = {}
for row in coordinator['rows']:
    path = Path(row['output_path'])
    assert row['status'] == 'completed_verified_bound_terminal_audit' and digest(path) == row['output_sha256']
    assert digest(Path(row['entry'])) == row['entry_sha256'] and digest(Path(row['log_path'])) == row['log_sha256']
    audits[Path(row['entry']).name[:2]] = json.loads(path.read_text('utf8'))
quality, local, cumulative = audits['45'], audits['44'], audits['22']
assert len(quality['rows']) == len(local['rows']) == len(cumulative['rows']) == 16
summary = quality['summary']
events = record['routes'][0]['events']
states = dict(Counter(e['status'] for e in events))
published = sum(e['status'] == 'published' for e in events)
assert record['new_publications'] == published and record['reused_publications'] == 0
geometry_rows = [row for row in cumulative['rows'] if row['candidate_status'] == 'published']
peak = max((row['geometry'][direction]['max_mm'] for row in geometry_rows for direction in ('area_forward', 'area_reverse')), default=None)
coverage = {threshold: min((row['geometry'][direction]['within_distance_fraction'][threshold]
    for row in geometry_rows for direction in ('area_forward', 'area_reverse')), default=None) for threshold in ('0.05', '0.1', '0.15', '0.2')}
topology = sum(row.get('topology_matches_reference', False) for row in geometry_rows)
bone_ledger = float(Fraction(*map(int, record['committed_bone_quality_ledger_fraction'])))
patch_ledger = float(Fraction(*map(int, record['committed_patch_quality_ledger_fraction'])))
directory = workspace/'初步实验/Geogram与PaMO组合验证'
number = max(int(m.group(1)) for p in directory.glob('*.md') if (m := re.match(r'^(\d+)-', p.name)))+1
assert number == 212
report = directory/f'{number:02d}-Geogram共享边竞争生成真实CT十六刀终态与完整复审.md'
stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日 %H:%M:%S（北京时间）')
# 三条数量曲线区分当前同输入的直接收益与跨父链表现，邻域和成本另列。
font = FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
steps = [r['step']+1 for r in quality['rows']]
same_old_counts = []
for row in quality['rows']:
    old = next((s for s in row.get('same_input', {}).get('strategies', []) if s['strategy'] == 'old_batch' and 'measured' in s), None)
    same_old_counts.append(old['measured']['whole']['below_10_deg']['faces'] if old else float('nan'))
figure, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True, constrained_layout=True)
for name, label, color in [('baseline', '206号旧路线', '#757575'), ('new', '本轮已发布路线', '#176b87')]:
    counts = [r.get(name, {}).get('whole', {}).get('below_10_deg', {}).get('faces', float('nan')) for r in quality['rows']]
    proxy = [100*r[name]['tool_box_centroid_proxy']['below_10_deg']['fraction'] if name in r else float('nan') for r in quality['rows']]
    cost = [r.get(name+'_client_pipeline_ms', float('nan'))/1000 for r in quality['rows']]
    for axis, values in zip(axes, (counts, proxy, cost)):
        axis.plot(steps, values, marker='o', markersize=3, color=color, label=label, linewidth=1.6)
axes[0].plot(steps, same_old_counts, color='#cb7820', linestyle=':', label='本轮当刀同输入旧策略', linewidth=1.6)
for axis, title, ylabel in zip(axes,
    ('小角面数量与父链差异', '同工具质心代理邻域的小角比例', '完整客户端管线成本'),
    ('小于10度面数', '比例（%）', '秒')):
    axis.set_title(title, fontproperties=font)
    axis.set_ylabel(ylabel, fontproperties=font)
    axis.grid(alpha=.2)
    axis.legend(prop=font)
axes[-1].set_xlabel('切削刀次', fontproperties=font)
axes[-1].set_xticks(steps)
figure_path = here/'14-连续质量与成本实际终态曲线.png'
figure.savefig(figure_path, dpi=160)
plt.close(figure)
table = ['|刀次|状态|当刀旧策略小角面|最终小角面|选择|206号路线小角面|', '|---|---|---:|---:|---|---:|']
for row in quality['rows']:
    same = row.get('same_input', {})
    strategy = next((s for s in same.get('strategies', []) if s['strategy'] == 'old_batch' and 'measured' in s), None)
    old = strategy['measured']['whole']['below_10_deg']['faces'] if strategy else '未执行'
    new = row.get('new', {}).get('whole', {}).get('below_10_deg', {}).get('faces', '未返回')
    baseline = row.get('baseline', {}).get('whole', {}).get('below_10_deg', {}).get('faces', '未返回')
    table.append(f"|{row['step']+1}|{row['new_status']}|{old}|{new}|{same.get('selected_strategy','无')}|{baseline}|")
scope = summary['tool_box_centroid_proxy']
whole = summary['whole']
text = f'''# Geogram共享边竞争生成真实CT十六刀终态与完整复审

生成时间：{stamp}

修改时间及修改内容：{stamp}，首次记录十六事件完整终态、六项实际复审、同源额外收益、连续路线质量与成本及复用资产。

文档概述：新父链发布{published}/16，拒绝与阻断均保留；同输入收益与不同父链路线比较分别解释。运行结束不自动证明连续质量优势或原创算法。

索引目录：1.完整执行；2.同源与路线质量；3.几何和账本；4.成本；5.研究结论与复现。

## 1. 完整执行与实际父链

从相同CT初态与十六仿真工具重新执行，零前缀复用；每刀接本轮已发布网格。完整状态为{states}，新发布{published}，复用0。实际父链、输出标签及保存摘要通过核对，终态记录在[实际连续目录]({study.as_posix()})。

206号旧路线发布{baseline_published}/16，本轮发布{published}/16。第十五刀Geogram和共同生成入口均正常退出，但生成阶段拒绝；第十六刀因前一步未发布而阻断。完整记录终态不等于十六刀全部成功，拒绝后没有用旧路线网格接续。

第十五刀最终初始对象剩一张面积{refusal_face['area_mm2']:.12g}平方毫米、最小角{refusal_face['minimum_angle_deg']:.9g}度的面，低于冻结的1e-12平方毫米门槛。该面坐标有限且准确叉积非零；初始对象的点、面和标签与已通过精确嵌入检查的最后接受翻边对象逐数组一致。它属于数值面积门槛拒绝，不直接证明数学退化、非闭合或Geogram内核错误。原拒绝保持，未取消门槛重判成功。

这个面是工具来源新面；同来源邻面翻边会产生另一张更小面积面，另两条边跨来源且新对角线已存在或重复顶点，当前简单翻边没有合法修复。拒绝发生在共同前置生成，尚未运行本刀共享边竞争；此前父状态变化可能影响后续输入，不能据拒绝时点将根因单独归给匹配策略。保存定位见[终态与文献核对目录]({here.resolve().as_posix()})内15至18号只读诊断。

六项复审分别检查保存对象及真实父链、骨面翻边准确证书与发布额度账本、来源精确零面及收缩证书、全部实际策略及选择账本、同初态同工具累计参照分布、质量及成本。复审按冻结入口实际执行，均与同一生成终态摘要绑定；不存在只准备入口就算完成的项。

全部实际策略调用{local['actual_strategy_calls']}次，无冲突策略最终选择{local['selected_nonconflicting']}次；未采用候选也保存并核对。生成方法与参数在连续路线开始后未改，未调用GPU或重跑旧成功帧。

## 2. 同源直接收益与连续路线比较

{chr(10).join(table)}

![同输入策略与连续路线质量成本曲线]({figure_path.as_posix()})

曲线取全部十六事件，未返回对象处留空，不用成功子集补齐缺失刀。橙色与本轮蓝色来自当刀同一输入，灰色描述206号独立父链；工具代理邻域和完整成本分别展示。

当刀当前输入上的旧策略与最终选择相比，小角绝对数量新增改善{summary['same_input_extra_bad_count_improved_events']}刀，真实坏面面积新增改善{summary['same_input_extra_bad_area_improved_events']}刀。统一规则要求数量和面积均不恶化，但保留旧结果的刀不能计作新机制改善；小角数略降而面积升高也不会被采用。

相对206号旧路线，在{summary['paired_published_events']}个配对发布帧中，全网格小角数更少{whole['new_bad_count_less_events']}刀、更多{whole['new_bad_count_more_events']}刀。新旧实际父状态可能不同，这个比较描述整条路线表现，不能用来替代当刀同输入的直接归因。

全网格小于10度比例新/旧中位数为{whole['new']['below_10_fraction_median']}/{whole['baseline']['below_10_fraction_median']}。同一工具包围盒外扩0.1毫米内面质心的代理邻域，新/旧中位数为{scope['new']['below_10_fraction_median']}/{scope['baseline']['below_10_fraction_median']}、最大值为{scope['new']['below_10_fraction_max']}/{scope['baseline']['below_10_fraction_max']}。这些值为0至1的比例，乘100得到百分比；代理邻域不是准确变化集合。

完整JSON另含小于5度和1度数量/占比/真实面积、总面数和面积。报告不以增加好面稀释占比，也不遗漏恶化帧。

## 3. 保存几何、累计参照与局部账本

已发布对象对同初态及同一工具序列的独立重放参照，拓扑相符{topology}/{len(geometry_rows)}。双向面积样本峰值为{peak}毫米；0.05、0.1、0.15、0.2毫米内的最低面积样本比例分别为{coverage}。这些是离散工具和经过有界修复的同内核参照上的抽样分布，另保留全顶点和分位数，不是物理连续扫掠证书。

骨面已提交额度账本为{bone_ledger:.12g}毫米，局部生成已提交表面界账本为{patch_ledger:.12g}毫米。局部准确表面界按保存双精度坐标的投影方向、有向边界与仿射平面残差独立复算；未发布事件不提交额度。两本账不能相加后冒充整路线CSG传播误差证书。

按用户要求完整报告几何分布，不固定0.1毫米峰值拒绝门槛或接受比例。静态闭合嵌入检查与连续运动认证的范围分别保留。

## 4. 完整客户端成本

上述{summary['paired_published_events']}个配对发布帧的新/旧客户端管线秒数分布分别为{summary['new_client_pipeline_seconds']}和{summary['baseline_client_pipeline_seconds']}，包含各自生成、保存、传输与发布检查。完整批次记录起止时段秒数为{batch_seconds}，另计入初态检查、拒绝尝试及状态记录；两者计时边界不同，批次时段仍不含连接关闭之后或显示渲染成本。

两路线为实际独立执行，不把单次时序观测视为随机化性能实验；多运行一个策略的成本计入新入口，不作无依据的加速结论。缺失两刀的发布成本不能用已成功帧中位数填补。

## 5. 当前研究结论与复现

当前成果是固定Geogram切削输出上的共享边质量生成候选，以及完整的同源、结构和连续取舍证据。210号九新参数有三例额外改善，211号已核对已有方法；本报告完整保留连续收益与负结果。普通输入上完整PaMO仍有更好的质量结果，不能据这些试验宣称全面优胜、任意输入保证或原创三角化内核。

本版覆盖低于206号旧候选，不能据静态好例直接替换旧版本。当前生成器需要进一步解决来源交界处的极小面，或另行论证面积门槛与实际数值稳定性的关系；两者都需显式新版本及验证，不能在本轮已打开路线中修改判定来改写14/16。

完整资产v125保存实际初态、全部工具、源码、全部策略输出、私有轨迹、拒绝和复审。沿用现有隔离bootstrap运行，不含连接凭据；资产用于复用和回归，不恢复本轮输入的未见身份。外部运行依赖及原始路径通过归档索引对应，未声明独立可移植安装。
'''
asset = evidence/'可复用磨削测试集/Geogram共享边竞争生成真实CT十六刀完整终态_v125'
asset.mkdir()
shutil.copytree(study, asset/'完整连续研究', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
shutil.copytree(here, asset/'终态顺序执行与文献核对', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
inputs = asset/'冻结初态与工具'
inputs.mkdir()
for item in [{'path': manifest['initial'], 'sha256': manifest['initial_sha256']}]+manifest['tools']:
    source = Path(item['path'])
    assert digest(source) == item['sha256']
    shutil.copy2(source, inputs/source.name)
dependencies = asset/'外部运行依赖'
dependencies.mkdir()
mapping = []
for source_path, expected in manifest['modules'].items():
    source = Path(source_path)
    if source.is_relative_to(study):
        continue
    destination = dependencies/f'{len(mapping)+1:03d}-{source.name}'
    shutil.copy2(source, destination)
    assert digest(destination) == expected
    mapping.append({'original_path': str(source), 'archived_path': destination.relative_to(asset).as_posix(), 'sha256': expected})
save(asset/'02-外部运行依赖原路径对应.json', {'生成时间': stamp, '修改时间及修改内容': '首次保存外部冻结依赖路径对应',
    '文档概述': '实际源码归档，不含环境凭据或完整第三方安装', '索引目录': ['rows'], 'rows': mapping})
# 累计参照的实际几何也入资产，避免只有摘要或另一个目录路径而缺少复用对象。
references = asset/'累计独立参照'
references.mkdir()
reference_mapping = []
for row in cumulative['rows']:
    source = Path(row['reference_path'])
    assert digest(source) == row['reference_sha256']
    destination = references/f'{row["step"]+1:02d}-累计参照.obj'
    shutil.copy2(source, destination)
    reference_mapping.append({'step': row['step'], 'original_path': str(source),
        'archived_path': destination.relative_to(asset).as_posix(), 'sha256': digest(destination)})
save(asset/'03-累计参照实际对象路径对应.json', {'生成时间': stamp, '修改时间及修改内容': '首次保存十六实际累计参照对象对应',
    '文档概述': '同内核有界修复参照，不是独立物理真值', '索引目录': ['rows'], 'rows': reference_mapping})
(asset/report.name).write_text(text, 'utf8')
files = [{'path': p.relative_to(asset).as_posix(), 'sha256': digest(p), 'bytes': p.stat().st_size}
    for p in sorted(asset.rglob('*')) if p.is_file()]
save(asset/'01-资产索引与摘要.json', {'生成时间': stamp, '修改时间及修改内容': '首次完整连续实际策略及六项复审归档',
    '文档概述': '完整十六事件及全部实际策略，不删除拒绝和未采用输出', '索引目录': ['files'], 'files': files})
for row in files:
    assert digest(asset/row['path']) == row['sha256']
report.write_text(text, 'utf8')
assert digest(report) == digest(asset/report.name)
root = workspace/'研究内容1-创新点.md'
old_root = root.read_bytes()
backup = here/'13-研究内容创新点连续终态更新前备份.md'
shutil.copy2(root, backup)
assert backup.read_bytes() == old_root
prefix = f'''> **本次进展记录生成时间**：{stamp}
> **修改时间及修改内容**：{stamp}，追加共享边竞争十六事件终态、六项复审、质量与成本完整结果。
> **文档概述**：新发布{published}/16，同输入与跨父链路线分别报告，保留恶化帧及研究边界。
> **索引目录**：实际父链；完整质量；累计几何分布；成本与复现。

- 完整状态{states}；六项实际终态复审完成，零前缀复用。
- 同源小角数额外改善{summary['same_input_extra_bad_count_improved_events']}刀；相对206号全网格更少{whole['new_bad_count_less_events']}刀、更多{whole['new_bad_count_more_events']}刀，不混为同刀因果收益。
- 生成与检查的完整客户端分布和几何分布保留，不声明净加速、任意输入或全面PaMO优势。
- 完整结果见[212号连续终态]({report.as_posix()})，实际策略与复审资产v125完成逐文件摘要核对。

'''
root.write_bytes(prefix.encode('utf8')+old_root)
assert root.read_bytes().endswith(old_root)
save(here/'12-连续完整结果汇报与复用归档回执.json', {'生成时间': stamp,
    '修改时间及修改内容': '首次记录完整连续终态汇报及逐文件归档核对',
    '文档概述': '执行批次与有限范围证据完整，研究优势依实际结果判断',
    '索引目录': ['report', 'asset'], 'status': 'completed_full_continuous_report_and_archive_verified',
    'report': str(report), 'report_sha256': digest(report), 'asset': str(asset), 'asset_files': len(files),
    'source_record_sha256': digest(rp), 'six_audits_sha256': digest(coordinator_path), 'published_events': published,
    'actual_strategy_calls': local['actual_strategy_calls'], 'summary': summary,
    'baseline_published_events': baseline_published, 'full_batch_recorded_duration_seconds': batch_seconds,
    'refusal_diagnosis_sha256': digest(diagnosis_path), 'refusal_equivalence_sha256': digest(equivalence_path),
    'cumulative_area_peak_mm': peak, 'cumulative_area_coverage': coverage,
    'GPU_calls': 0, 'new_generation_calls': 0})
print('212号完整连续结果与资产逐文件核对完成', len(files), '文件', flush=True)
