"""只在两批真实终态及完整保存复审后生成间歇维护最终比较。"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import numpy as np
from cadence_policy import POLICIES
from audit_followup_candidate import sha256
from run_geometry_study import now,save


def load_verified(batch):
    frozen=json.loads((batch/'01-方法与调度冻结.json').read_text(encoding='utf-8'))
    report=json.loads((batch/'03-批次环境与完整分母.json').read_text(encoding='utf-8'))
    audit=json.loads((batch/'05-完整记录与调度绑定复核.json').read_text(encoding='utf-8'))
    reaudit=json.loads((batch/'06-保存对象完整复审'/'01-保存对象完整复审.json').read_text(encoding='utf-8'))
    slivers=json.loads((batch/'07-近退化参照只读归因.json').read_text(encoding='utf-8'))
    digest=sha256(batch/'04-逐刀真实父反馈记录.jsonl')
    if report['status']!='completed_with_recorded_outcomes' or reaudit['status']!='completed':raise ValueError('仍有未完成批次')
    if audit['ledger_sha256']!=digest or reaudit['ledger_sha256']!=digest:raise ValueError('复审不绑定同次终态')
    if slivers['ledger_sha256']!=digest:raise ValueError('参照归因不绑定同次终态')
    if audit['checked_events']!=report['planned_events'] or audit['published']!=reaudit['published_reaudited']:raise ValueError('完整复审分母不符')
    if not all(r['original_decision_consistent'] for r in reaudit['rows']):raise ValueError('发布决策不一致')
    for row in frozen['files']:
        if sha256(batch/'runtime'/row['file'])!=row['sha256']:raise ValueError('冻结实际源码改变')
    reaudit['sliver_diagnostic']=slivers
    return frozen,audit,reaudit


def compare(summaries):
    indexed={(r['route'],r['round'],r['policy']):r for r in summaries}
    aggregate=[];pairs=[]
    for policy in POLICIES:
        rows=[r for r in summaries if r['policy']==policy]
        speeds=[]
        for row in rows:
            baseline=indexed[(row['route'],row['round'],'every')]
            # 只用同一路线同轮次两边完整且未观测其他GPU进程的结果估计速度。
            if policy!='every' and baseline['complete'] and row['complete'] and not baseline['gpu_other_process_observed'] and not row['gpu_other_process_observed']:
                ratio=baseline['total_execution_ms']/row['total_execution_ms']
                speeds.append(ratio)
                pairs.append(dict(route=row['route'],round=row['round'],policy=policy,speedup=ratio,
                    baseline_ms=baseline['total_execution_ms'],policy_ms=row['total_execution_ms'],
                    baseline_calls=baseline['maintenance_calls'],policy_calls=row['maintenance_calls'],
                    baseline_p95_ms=baseline['p95_ms'],policy_p95_ms=row['p95_ms'],
                    baseline_final_quality=baseline['final_quality'],policy_final_quality=row['final_quality'],
                    policy_intermediate_angle10_fraction=row['maximum_published_angle10_fraction'],
                    policy_intermediate_angle10_area_fraction=row['maximum_published_angle10_area_fraction']))
        statuses=Counter();causes=Counter()
        for row in rows:
            statuses.update(row['status_counts']);causes.update(row.get('candidate_rejection_cause_counts',{}))
        aggregate.append(dict(policy=policy,planned_route_rounds=len(rows),complete_route_rounds=sum(r['complete'] for r in rows),
            planned_events=sum(r['planned'] for r in rows),published=sum(r['published'] for r in rows),status_counts=dict(statuses),
            executed_maintenance_calls=sum(r['maintenance_calls'] for r in rows),mandatory_repairs=sum(r['mandatory_repairs'] for r in rows),
            candidate_rejection_cause_counts=dict(causes),
            final_flushes=sum(r['final_flushes'] for r in rows),full_paired_comparisons=len(speeds),
            median_full_paired_speedup=float(np.median(speeds)) if speeds else None))
    return aggregate,pairs


def run(root):
    dev,da,dr=load_verified(root/'开发96事件');evaluation,ea,er=load_verified(root/'保留864事件')
    if dev['files']!=evaluation['files'] or dev['adaptive']!=evaluation['adaptive']:raise ValueError('开发及评价方法不一致')
    if da['planned_events']!=96 or ea['planned_events']!=864:raise ValueError('原计划范围未完整执行')
    aggregate,pairs=compare(ea['summaries'])
    stamp=now()
    display_stamp=datetime.fromisoformat(stamp).strftime('%Y年%m月%d日%H时%M分%S秒')
    result=dict(time_beijing=stamp,scope='96开发及864保留计划事件；六条评价路线两次技术重复，不是12独立患者',
        development=dict(events=da['checked_events'],published=da['published'],saved_reaudited=dr['checked_candidates']),
        evaluation=dict(events=ea['checked_events'],published=ea['published'],saved_reaudited=er['checked_candidates'],aggregate=aggregate,pairs=pairs,
            invalid_reference_slivers=er['sliver_diagnostic']['rows']),
        source_hashes=dict(development_audit=sha256(root/'开发96事件'/'05-完整记录与调度绑定复核.json'),
            evaluation_audit=sha256(root/'保留864事件'/'05-完整记录与调度绑定复核.json'),
            evaluation_saved_audit=sha256(root/'保留864事件'/'06-保存对象完整复审'/'01-保存对象完整复审.json'),
            evaluation_sliver_audit=sha256(root/'保留864事件'/'07-近退化参照只读归因.json')))
    save(root/'10-完整范围配对比较与证据绑定.json',result)
    text=f'# 间歇质量维护完整验证结果\n\n生成时间：{display_stamp}（北京时间）\n修改时间：{display_stamp}（北京时间）\n修改内容：首次汇总全部终态及保存复审。\n\n'
    text+='## 文档概述\n\n验证连续切削中减少完整作者PaMO调用能否降低总流程成本，并记录质量与可靠性代价。\n\n## 索引目录\n\n1. 完整范围及证据\n2. 保留评价汇总\n3. 完整配对速度与质量\n4. 解释边界\n\n'
    text+=f"## 1. 完整范围及证据\n\n开发96/96、保留864/864计划事件记录及父链核对；实际保存候选分别{dr['checked_candidates']}及{er['checked_candidates']}全部重新复审，发布分别{da['published']}及{ea['published']}。失败和后缀受阻保留。开发与评价{len(dev['files'])}份冻结源码相同。详见各批05号及06目录01号，汇总摘要绑定见本目录10号。\n\n"
    text+='## 2. 保留评价汇总\n\n|策略|完整路线轮次/计划|发布事件/计划|已执行维护次数|强制修复|末帧补维护|完整配对数|完整配对加速中位数|\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
    for row in aggregate:
        speed='无完整配对' if row['median_full_paired_speedup'] is None else f"{row['median_full_paired_speedup']:.3f}倍"
        text+=f"|{row['policy']}|{row['complete_route_rounds']}/{row['planned_route_rounds']}|{row['published']}/{row['planned_events']}|{row['executed_maintenance_calls']}|{row['mandatory_repairs']}|{row['final_flushes']}|{row['full_paired_comparisons']}|{speed}|\n"
    text+='\n调用次数含失败尝试，失败策略执行更短，不能只按总调用少认定效率更高。两轮为技术重复，仍只有六条评价路线。\n\n## 3. 完整配对速度与质量\n\n|路线|轮次|策略|总流程加速|单刀P95秒|中间最高<10°面/面积比例|末帧<10°面/面积比例|\n|---|---:|---|---:|---:|---:|---:|\n'
    for row in pairs:
        q=row['policy_final_quality']['angle_below_10_deg']
        text+=f"|{row['route']}|{row['round']}|{row['policy']}|{row['speedup']:.3f}倍|{row['policy_p95_ms']/1000:.3f}|{row['policy_intermediate_angle10_fraction']*100:.3f}% / {row['policy_intermediate_angle10_area_fraction']*100:.3f}%|{q['fraction']*100:.3f}% / {q['area_fraction']*100:.3f}%|\n"
    text+='\n5°、1°、严格25°和q≥0.4、面数、末帧基线、几何距离及逐帧质量均保存在原始记录和10号配对数据，不用末帧替代中间质量。各批05号另含累计参照名义去除量，跨无效参照不补算单刀去除量。\n\n## 4. 解释边界\n\n时间含Geogram、共同清理、检查、质量/几何审计、完整PaMO进程与SSH传输；离线累计工具参照准备排除，不是单纯CUDA或真实跟踪渲染系统的实时延迟。末帧补维护和强制有效性修复计入。配对仅用同一路线同轮次完整执行且采样时未观测其他GPU进程的结果；不将不同长度有效子集相除，采样也不是设备全程独占证书。\n\n自适应阈值为冻结探索配置，尚无局部邻域触发或最优性证明。质量分布是统计和触发量，没有恢复全三角形25°硬门槛。几何0.1毫米预算使用双向样本及全部顶点探针，不是连续Hausdorff证书。参照共享Geogram与表示清理，不是算法独立真值。公开骨面已见，尺度人为归一到100毫米，新轨迹不是未见患者或真实临床轨迹；工具离散误差未认证。\n'
    (root/'09-间歇质量维护完整验证结果.md').write_text(text,encoding='utf-8')
    print('完整结果已生成',da['checked_events']+ea['checked_events'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    run(parser.parse_args().root)
