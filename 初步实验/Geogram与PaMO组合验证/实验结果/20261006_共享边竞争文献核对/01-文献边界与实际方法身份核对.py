"""核对实际运行源码与已有方法，保存研究边界，不改运行中的候选或评价参数。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import shutil


def digest(path):
    """对实际文件字节计算摘要，绑定说明与已冻结的方法身份。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


workspace = Path.cwd()
here = Path(__file__).parent
evidence = Path('D:/GraduationProject_切削排斥证据')
study = evidence/'20261006_Geogram共享边竞争生成真实CT连续验证'
mp = study/'43-共享边竞争生成真实CT十六刀冻结清单.json'
manifest = json.loads(mp.read_text('utf8'))
paths = [study/'02-共享边竞争生成单刀隔离运行.py',
    study/'无冲突候选版本/全部分量保护生成/02-共享边同步分级.py',
    study/'无冲突候选版本/全部分量保护生成/03-活动分量过滤共面生成.py']
for path in paths:
    assert digest(path) == manifest['modules'][str(path)]
split_code, generator_code = [p.read_text('utf8') for p in paths[1:]]
assert 'faces.isdisjoint(occupied)' in split_code
assert split_code.index('selected = select_disjoint_edges') < split_code.index('selected.difference_update')
assert 'pYYq20S{max_added_per_region}Q' in generator_code and 'max_added_per_region=128' in generator_code
static = evidence/'20261006_Geogram共享边竞争生成独立参数验证'
static_rp = static/'九新参数完整对照/01-九新参数实际策略与完整对照记录.json'
static_ap = static/'完整保存与选择独立复审/01-九新参数全部实际策略与统一选择复审.json'
record, audit = [json.loads(p.read_text('utf8')) for p in (static_rp, static_ap)]
assert record['status'] == 'completed_with_all_nine_parameter_outcomes'
assert audit['status'] == 'completed_all_nine_cases_all_actual_strategies_and_selection_verified'
assert audit['source_record_sha256'] == digest(static_rp)
assert record['actual_strategy_calls'] == audit['actual_strategy_calls'] == 15
assert len(record['rows']) == 9
improved = [(r['old_batch']['quality']['angle_below_10_deg']['faces'],
    r['competing_selected']['quality']['angle_below_10_deg']['faces']) for r in record['rows']
    if r['competing_selected']['quality']['angle_below_10_deg']['faces'] < r['old_batch']['quality']['angle_below_10_deg']['faces']]
assert improved == [(9, 6), (5, 4), (583, 5)]
directory = workspace/'初步实验/Geogram与PaMO组合验证'
number = max(int(m.group(1)) for p in directory.glob('*.md') if (m := re.match(r'^(\d+)-', p.name)))+1
assert number == 211
stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日 %H:%M:%S（北京时间）')
report = directory/f'{number:02d}-Geogram共享边质量生成文献核对与创新边界.md'
text = f'''# Geogram共享边质量生成文献核对与创新边界

生成时间：{stamp}

修改时间及修改内容：{stamp}，首次核对已有三角化、细化冲突处理和PaMO方法，明确当前候选的实际实现及可支持的贡献。

文档概述：改善切削后三角形生成具有实测依据；共面重铺、无冲突细分和候选择优本身不足以证明新算法。当前贡献应围绕切削约束下的几何保持与质量改善展开。

索引目录：1.研究问题；2.已有方法与本版区别；3.实测收益及限制；4.收尾判断。

## 1. 改善切削质量的实测依据

208号的三普通切口在切削前均无小于10度面，原始Geogram切削后出现60、55、54个；两个孔模型切削前已有各1728个差面。研究应分别评价切削新生差面和输入继存差面，避免把修复背景网格的收益全归给切削生成机制。见[208号来源诊断](208-Geogram切削新增差面与原网格差面来源诊断.md)。

本版是在固定Geogram切削输出上改进共享边采样和局部质量生成。第三方Geogram内核及二进制保持原版；源码继承和组合适配不能称为已经改写作者CSG算法。算法研究可以先在独立模块中验证，只有出现可归因收益后才有依据考虑内核集成。

## 2. 已有方法与本版实际区别

|已有方法|已具备的能力|本版区别与贡献边界|
|---|---|---|
|Geogram约束三角化与共面简化|交线约束三角化；提取共面区域边界并重新三角化|保留来源分界，改进区域共享边采样；共面重铺本身已有|
|Triangle质量生成|角度目标、边界补点控制和新增点预算|共享边由外层同步处理，内部生成仍使用Triangle；不是新三角化内核|
|自适应细化的独立集处理|解决同轮局部操作的冲突已有研究|本版按长度失衡贪心选边，每个原面一轮至多分裂一边；不是首创无冲突选择|
|PaMO独立区域与安全投影|独立区域并行收缩；碰撞约束下优化顶点位置|本版是CPU共享边分裂与区域重铺，没有继承PaMO的GPU并行或连续碰撞保证|

Geogram作者在2.2.4节已经处理共面区域合并及重新约束三角化，其主要贡献还包括准确交点坐标上的约束Delaunay三角化。论文另明确区分准确坐标与转为浮点坐标的处理。因此，本项目保存双精度对象上的检查不能直接当作作者准确坐标算法的保证或失效结论。[Geogram作者论文](https://arxiv.org/html/2405.12949v2)

当前实际区域生成参数为`pYYq20S128Q`：`q20`请求20度质量目标，`YY`禁止在所有约束线段上新增点，`S128`限制新增点数。Triangle文档说明输入线段之间的真实小角不能由质量约束消除。由此推断，受限制的边界和新增点预算可能使角度目标无法全部实现；20度是生成目标，不能作为每个返回面都达标的证书。[Triangle参数说明](https://www.cs.cmu.edu/~quake/triangle.switch.html)，[质量约束说明](https://www.cs.cmu.edu/~quake/triangle.quality.html)

细化时用独立集解决并发更新冲突已有先例。当前源码按边长相对目标长度排序，限制被选边涉及的原面集合互不重叠；它没有实现该文的最长边传播及前缀计算流程，不能沿用其角度、终止或性能结论。这个区别支持识别本版操作，但不能单靠区别证明新颖性。[最长边细化论文摘要](https://epubs.siam.org/doi/10.1137/140973840)

PaMO第5.1节用一环邻域确定独立收缩区域，第6节在连接关系固定时进行碰撞约束的顶点优化。独立区域、质量代价和安全投影都已有方法；当前候选的严格局部源面保持与切削场景表现需要用自己的证据支持。[PaMO作者论文](https://arxiv.org/html/2509.05595v1)

## 3. 已有收益与仍需解释的代价

210号九新参数完整对照实际执行15次策略生成，三例小角数9→6、5→4、583→5，其余六例保留旧结果。全部实际候选、包括未采用输出，已作保存复审。这个结果支持特定输入上的额外收益；九例不恶化部分由择优规则保障，不等于九例都获得新增改善。见[210号完整对照](210-Geogram共享边竞争生成九新参数完整验证与连续启动.md)。

两个孔开发结果的大幅改善同时增加了面数；另一普通切口和薄壁曾退步。共享边竞争为退步输入保留旧结果，但多运行一份生成器增加成本。评价须同时报告小角数量、占比、坏面实际面积、面数、特征保持、几何分布及时间，不能仅用增加好面稀释占比。

目前可支持的贡献是切削后局部质量生成候选、其来源约束及保存几何核查，以及实测的质量和结构取舍。完整原版PaMO在部分普通切口与CT上的质量仍更好；当前证据不足以写成全面超过PaMO或原创三角化算法。

## 4. 当前收尾判断

继续完成已冻结十六刀实际父网格反馈和六项终态复审，不在这条已打开路线中调参。同输入旧策略与新策略用于判断该轮生成改动的直接收益，跨路线终态用于判断连续表现；两者不能混为因果证据。

最终说明应围绕“保持切口形状和小特征时，能否减少连续切削产生的细长面”给出完整结果与成本。若连续优势仍不稳定，应保留这个候选和负结果，避免把运行结束写成算法目标已经实现。原有局部连续表面界只覆盖当刀保存输入到维护输出，不等于整条CSG传播或物理扫掠的误差保证。
'''
report.write_text(text, 'utf8')
assert report.read_text('utf8') == text
root = workspace/'研究内容1-创新点.md'
original_root = root.read_bytes()
backup_dir = directory/'备份/211号文献核对更新前'
backup_dir.mkdir(parents=True)
backup = backup_dir/'01-研究内容创新点原字节备份.md'
shutil.copy2(root, backup)
assert backup.read_bytes() == original_root
prefix = f'''> **本次进展记录生成时间**：{stamp}
> **修改时间及修改内容**：{stamp}，追加共享边生成与已有方法的关系及当前创新表述边界。
> **文档概述**：主问题仍为减少切削后细长面并保住实际几何；无冲突选择和共面重铺不单独作为原创算法。
> **索引目录**：已有方法；实际候选身份；质量与成本证据；连续收尾。

- 本版在固定Geogram输出上改善共享边采样与局部生成，第三方内核未改；Triangle仍承担区域质量生成。
- 九新参数三例新增改善，其余保留旧版；不能由择优保障的不恶化推导普遍质量优势。
- 最终贡献须由切削几何保持、特征和质量收益及成本支持，十六刀完整终态与复审仍待取得。
- 依据和文献见[211号创新边界]({report.as_posix()})；历史实验数字与冻结方法保持。

'''
root.write_bytes(prefix.encode('utf8')+original_root)
assert root.read_bytes().endswith(original_root)
receipt = {'生成时间': stamp, '修改时间及修改内容': '首次保存文献核对、实际方法绑定和本地说明',
    '文档概述': '文献与当前源码及已终态静态对照核对；不新增维护调用或连续成功分母',
    '索引目录': ['sources', 'files'], 'status': 'completed_literature_and_actual_method_scope_note',
    'GPU_calls': 0, 'new_generation_calls': 0, 'generation_manifest_sha256': digest(mp),
    'static_record_sha256': digest(static_rp), 'static_audit_sha256': digest(static_ap),
    'sources': ['https://arxiv.org/html/2405.12949v2',
        'https://www.cs.cmu.edu/~quake/triangle.switch.html',
        'https://www.cs.cmu.edu/~quake/triangle.quality.html',
        'https://epubs.siam.org/doi/10.1137/140973840', 'https://arxiv.org/html/2509.05595v1'],
    'files': [{'path': str(p), 'sha256': digest(p)} for p in paths+[report, root, backup, Path(__file__)]]}
(here/'02-文献核对与实际方法身份归档回执.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', 'utf8')
print('211号文献与实际方法身份核对完成，当前冻结源码未改', flush=True)
