"""从原始来源、GPU与审计记录生成本轮报告和静态权衡图。"""

from datetime import datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "实验结果"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    # 同目录29号已用于连续几何体检，本报告顺延为30号。
    destination = HERE / "30-布尔局部维护来源体检与GPU开发对照.md"
    if destination.exists() and not args.repair:
        raise FileExistsError(destination)
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日%H时%M分%S秒")
    generated = now
    if args.repair:
        # 修订保留最初生成时间，旧正文另存，不能改写消融初次输出和日志。
        previous = destination.read_text(encoding="utf-8")
        generated = re.search(r"\*\*生成时间\*\*：([^（]+)", previous).group(1).strip()
        backup = RESULTS / "20261004_局部维护八轮折叠开发/06-修正前开发报告.md"
        if not backup.exists():
            backup.write_text(previous, encoding="utf-8")
    diagnostic = read(RESULTS / "20261004_局部维护来源重放/03-来源三角化对照与局部体检.json")
    directories = [RESULTS / "20261004_局部维护保存帧开发", RESULTS / "20261004_局部维护八轮折叠开发"]
    batches = [read(d / "03-变化区域完整独立审计.json") for d in directories]
    ablations = read(RESULTS / "20261004_局部维护消融有效数字复核/02-有效数字消融独立审计.json")
    if any(batch["status"] != "completed" for batch in [*batches, ablations]):
        raise ValueError("审计未完成，不能生成完成记录")
    labels = {"full": "完整PaMO", "global": "全量两阶段", "spatial": "普通空间局部", "boolean": "布尔来源局部"}
    summary = {"time_beijing": now, "scope": "two_seen_development_routes_saved_frames_only", "budgets": [],
               "tests": {"core_actual_passed_before_roundtrip_fix": 90, "local_actual_passed_after_roundtrip_fix": 5,
                         "geogram_class_skipped": 1, "group_summary_without_failures": "18/18"},
               "independent_test_access": False, "local_C1_completed": False, "local_CT_completed": False}
    table = ["| 折叠预算 | 分支 | 条件性有效候选 | 维护均时ms | 全网格<10°比例帧中位数 | 变化区<10°比例帧中位数 |",
             "| --- | --- | --- | ---: | ---: | ---: |"]
    for budget, batch in zip((1, 8), batches):
        rows = []
        for method in labels:
            selected = [r for r in batch["rows"] if r["method"] == method]
            row = {"method": method, "accepted_sampled": sum(r["accepted_sampled"] for r in selected),
                   "executed": len(selected), "wall_mean_ms": float(np.mean([r["maintenance_wall_ms"] for r in selected])),
                   "all_angle_below_10_median_percent": float(np.median([r["quality"]["angle_below_10_deg"]["fraction"] * 100 for r in selected])),
                   "affected_angle_below_10_median_percent": float(np.median([r["quality_sweep_affected"]["angle_below_10_deg"]["fraction"] * 100 for r in selected])),
                   "sampled_geometry_max_mm": max(r["metrics"]["sampled_reference_geometry"]["sampled_max_mm"] for r in selected)}
            rows.append(row)
            table.append(f"| {budget} | {labels[method]} | {row['accepted_sampled']}/{len(selected)} | {row['wall_mean_ms']:.1f} | {row['all_angle_below_10_median_percent']:.4f}% | {row['affected_angle_below_10_median_percent']:.4f}% |")
        summary["budgets"].append({"collapse_pass_budget": budget, "methods": rows})
    summary["ablations"] = [{"method": method, "executed": len(rows),
                              "accepted_sampled_with_fixed_contract": sum(r["accepted_sampled"] for r in rows),
                              "external_contract_passed": sum(bool(r.get("fixed_contract", {}).get("passed")) for r in rows)}
                             for method in ("boolean_no_transition", "boolean_no_boundary")
                             for rows in [[r for r in ablations["rows"] if r["method"] == method]]]
    summary_path = directories[1] / "04-局部开发结果汇总.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    colors = dict(zip(labels, ("#254E70", "#9B6A6C", "#D69F3A", "#36806B")))
    for ax, budget, batch in zip(axes, (1, 8), batches):
        for method in labels:
            selected = [r for r in batch["rows"] if r["method"] == method]
            ax.scatter([r["maintenance_wall_ms"] for r in selected],
                       [r["quality"]["angle_below_10_deg"]["fraction"] * 100 for r in selected],
                       color=colors[method], label=labels[method], s=36, alpha=0.85)
        ax.set(xlabel="单帧维护墙钟（ms，不含布尔和独立审计）", ylabel="全网格 <10° 三角面比例（%）",
               title=f"最多{budget}次折叠：七张已见合法帧")
        ax.grid(alpha=0.18)
    axes[0].legend(fontsize=8)
    figure_path = directories[1] / "05-质量与维护代价权衡.png"
    figure.savefig(figure_path, dpi=160)
    plt.close(figure)
    active = [r["source_active_two_rings"]["fraction"] * 100 for r in diagnostic["rows"]]
    default_missing = []
    provenance = read(RESULTS / "20261004_局部维护来源重放/01-来源重放记录.json")
    for row in provenance["rows"]:
        if row["mode"] == "default":
            counts = row["operand_counts"]
            default_missing.append(int(counts.get("0", 0)) / sum(map(int, counts.values())) * 100)
    content = f"""# 30-布尔局部维护来源体检与GPU开发对照

> **生成时间**：{generated}（北京时间）  
> **修改时间及修改内容**：{generated}，首次生成；记录八帧来源诊断、固定边界CUDA算子、首帧试跑、1/8次折叠对照及边界/过渡带消融。{now}，修正OBJ固定小数位舍入的混杂，用17位有效数字复跑14张消融并重新独立审计；原输出、日志及首版正文保留。  
> **文档概述**：按37号协议执行已见开发体检。局部版本能保持指定外部面和固定顶点，并通过列明的拓扑及离散参照抽样检查；它尚未在相近质量下优于完整PaMO，布尔选域对普通选域的净效率收益也未成立。  
> **索引目录**：[一、实际完成](#一实际完成) · [二、来源与远区体检](#二来源与远区体检) · [三、算法与对照](#三算法与对照) · [四、GPU结果](#四GPU结果) · [五、边界与过渡带消融](#五边界与过渡带消融) · [六、验证与复现](#六验证与复现) · [七、停止与后续](#七停止与后续)

## 一、实际完成

本轮连接用户授权的实例，实测RTX4090、驱动595.71.05，设备上报显存49140 MiB；不据此推断零售硬件规格。复用既有Geogram库、PaMO虚拟环境和Torch2.8.0+cu128。仅在`locality_cuda_20261004/build_tools`安装Ninja1.13.0用于隔离扩展构建，未重装驱动、CUDA或作者主包，未关闭实例。

已完成16次来源布尔重放（八帧×默认/禁简化）、八帧完整局部性体检、固定外部折叠和受限安全投影实现、首帧四分支GPU试跑、两种预算各28张保存帧输出与独立审计，以及边界/过渡带消融14张、有效数字修正后复核14张。首帧与后续同输入复跑不增加独立样本数。两条路线仍是已见开发路线；保存帧对照不是新局部输出回灌的C1。

## 二、来源与远区体检

默认共面简化输出的来源0标签占面数{min(default_missing):.2f}%—{max(default_missing):.2f}%。作者简化源码创建新三角面后未同步填写`operand_bit`，不能把0当作父面。禁共面简化后八帧均只有来源1/2；按顶点和面心到所属操作数及来源交界顶点到双操作数的1e-8毫米数值检查八帧通过，属于数值核对而非一般精确保证。

工具面与来源交界邻面加两层邻域占面数{min(active):.2f}%—{max(active):.2f}%。按与算法活动掩码无关的累计物理扫掠和0.1毫米余量定义远区，旧完整PaMO单向8192面积样本最大漂移约0.00646—0.03187毫米；同时保存反向距离及最近面法向变化。不能把这些有限样本写成连续距离证书。

默认重放与历史输出不逐字节相同，但双向全部顶点/面心距离不超过约8.2e-15毫米，体积差不超过约3.6e-15立方毫米。禁简化与默认的同类距离不超过约8.2e-15毫米，仍没有完整连续证明。三角化面数变化很大，必须单列而不混入来源机制收益。

`stop_resume_e5`禁简化网格有2个自交报警面，作为输入拒绝保留。七张输入进入局部GPU开发，因此任何完整八帧覆盖计数最多7/8，不能只报合法帧分母而隐去上游问题。

## 三、算法与对照

CUDA副本仅增加固定顶点掩码：任一端点固定的边禁止折叠。原始索引随占用掩码重编号；投影在固定自由度子空间计算梯度和Hessian向量乘，碰撞能量、全网格BVH和CCD范围沿用作者实现。每次重编号后更新固定掩码，不能沿用旧编号。

阶段一SDF/DMC无法直接保留局部外部连接，故局部版本显式关闭阶段一；输入必须先通过合法性和FP32非退化门控。全量两阶段也关闭阶段一并使用同一扩展、相同折叠预算和五轮投影。普通局部只用工具AABB扩0.1毫米及两层面邻接，布尔局部用验证来源及两层邻接。两种局部均固定所有非活动面的顶点。所有分支共用相同来源完备网格，并享有CPU预加载及逐帧独立CUDA子进程。

固定坐标从FP32恢复为输入FP64；首帧最大恢复幅度约1.26e-7毫米，导出重载后核对完整外部三角面及绕序、固定点精确位置，再执行全网格独立审计。不是在投影后才用覆盖位置替代边界约束，也不宣称整个投影过程为FP64。

## 四、GPU结果

{chr(10).join(table)}

两种预算共56/56张候选通过列明的闭合、绕序、顶点流形、自交检测、非有限/退化和离散参照双向8192点抽样检查；42张两阶段候选的外部契约全部通过。小角比例仅统计，不作为有效性拒绝条件。统一连续几何预算仍未知。

八次折叠比一次减少部分小角面，仍不能达到完整PaMO的质量分布。八次预算布尔局部均时约1426毫秒，普通局部约1427毫秒，差值小于运行波动，不能宣称来源带来加速。布尔版本更多地保留原面；比例略低时必须同时看绝对小角面数和面积，不能只用面数分母判断优势。

计时只有一次按分支固定顺序的开发运行，包含fork、CUDA子进程及维护，但不包含来源布尔、输入打包、主机模块首次导入、独立审计、状态发布与显示。审计另记录并给出维护+审计时间；这些不是完整端到端性能结论，更不是独立路线统计显著性。完整PaMO的相同输入复跑也出现输出面数和尾部差异，正式比较仍须冻结版本后的路线级重复和交错顺序。

![七帧质量与维护代价](实验结果/20261004_局部维护八轮折叠开发/05-质量与维护代价权衡.png)

## 五、边界与过渡带消融

消融使用相同七张合法输入和八次折叠预算。无过渡带只使用布尔核心；无固定边界只固定活动面之外的独占顶点，使共享边界自由，仍执行完整碰撞检查。关闭固定契约后的候选即使闭合、几何抽样通过，也不能自动计为满足外部保真契约。

初次消融中，无过渡带的固定坐标在GPU内通过，却因OBJ固定17位小数截断极小坐标而在重载后仅1/7精确通过；该现象不能归因于过渡带。已改为17位有效数字，新增极小坐标逐值重载回归，并在新目录原样复跑全部14张。以下采用修正后结果，原始14张与审计保留为I/O反例。

"""
    for row in summary["ablations"]:
        content += f"- `{row['method']}`：执行{row['executed']}张，包含外部固定契约的条件性通过{row['accepted_sampled_with_fixed_contract']}/{row['executed']}，外部契约通过{row['external_contract_passed']}/{row['executed']}。\n"
    content += """
消融只能检验指定边界与连接规则；它不能抵消局部版本相对完整PaMO的小角尾部劣势，也不能证明局部机制一般适用。

## 六、验证与复现

首次本地统一核心回归实际90项通过；Geogram适配器类级跳过1次，原因是本机缺少作者可执行文件。18/18为无失败组汇总，不能解释为每组都实际完整执行。修正导出后新增的极小FP64坐标重载回归及原4项局部边界测试共5项通过，未重复把原4项计为新增测试数。发布控制接入统一核心后实际99项通过、19组无失败，适配器类级仍跳过1次；结果见`20261004_局部维护发布控制复核/02-本地回归结果.json`。源文件语法检查通过。

CUDA构建首轮缺Ninja、首帧加载首轮发生原版与副本的同名类型注册冲突，均保留失败日志；隔离副本改模块内注册后重编译成功，未改原版包。GPU输出及代码、输入、实际扩展、参照哈希均保存；审计不是“程序返回0即通过”。

复现入口：`run_locality_provenance.py`、`locality_diagnostic.py`、`prepare_locality_cuda.py`、`build_locality_cuda.py`、`package_locality_saved_batch.py`、`run_locality_saved_batch.py`、`audit_locality_saved_batch.py`。参数与哈希见各结果目录的01号清单；本机使用根目录`.venv/Scripts/python.exe`，远端复用原PaMO环境。凭据仅从忽略且限制ACL的`.env`读取，不进入上传包或报告。

## 七、停止与后续

当前停止本版的优势主张，不进入12条独立路线或真实CT扩大来寻找容易获胜的输入。已证明的内容是指定输入上的来源完备性数值核对、固定外部的算子实现及有效性；尚未证明相近质量下的效率优势或来源可归因收益。

低角残差归因已保存为`07-局部质量残差归因.json`。crossing_e0原有156个小角面中88个数值匹配父三角面且处于活动区外，八轮后仍原样保留；另19个残差属于修改后的几何或连接。crossing_e3八轮后205个小角面中26个外部原面保持不变、179个属于修改后的几何或连接。数值匹配使用1e-12毫米舍入键，只用于归因，不是严格对应证书。这说明初态继承质量和活动域内质量生成是两个问题，不能靠继续增加折叠次数解释全部差距。

`locality_feedback.py`已实现同一布尔输入上的0层尝试、一次2层扩域和完整PaMO回退，独立审计后才更新父版本；上游不合法或所有尝试失败时保留上一发布状态。所有重试与审计费用计入总耗时，并核对父快照和输入摘要。8项针对性测试覆盖小角面不拦截、扩域、回退、全失败、非法输入、证据缺项、执行异常及输入污染。用已保存网格重新独立审计的发布控制复核7/8发布，剩余输入拒绝；7个通过帧均在首个0层尝试接受，因此真实扩域/回退分支仍只有失败注入测试证据。该复核是C0保存帧控制检查，不是新的连续反馈，更不能称GPU执行器已接入此控制器。

下一步把发布控制器接入新局部C1执行器，同时设计真正的局部质量生成或有依据的质量驱动扩域；新的方法和预算必须预先登记，并在开发获得收益后再冻结进入独立评测。29号原版基线体检已查看原12条路线，新机制不能继续称这些输入未见独立集，必须另行冻结新独立输入。

新局部真实C1、全六条开发路线、独立12路线、新组合真实CT16/138段、在线状态年龄及完整连续几何界仍未完成。目标保持进行中，不用本报告的保存帧诊断替代这些交付。
"""
    destination.write_text(content, encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
