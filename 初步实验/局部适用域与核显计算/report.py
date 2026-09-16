"""从原始JSON生成20号报告；统计口径、数学前提与未完成事项一起保留。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import hashlib
import json
import sys
import numpy as np

ROOT = Path(__file__).parent
OUT = ROOT/'实验结果'
PROJECT = ROOT.parents[1]
sys.path.insert(0, str(ROOT.parent/'真实骨模型演示'))
from real_bone_demo import trajectory


def stats(values):
    return '/'.join(f'{v:.3f}' for v in [np.mean(values), np.percentile(values, 95),
                                       np.percentile(values, 99), max(values)])


if __name__ == '__main__':
    comparison = json.loads((OUT/'comparison.json').read_text(encoding='utf-8'))
    gpu = json.loads((OUT/'gpu.json').read_text(encoding='utf-8'))
    audit = json.loads((OUT/'audit.json').read_text(encoding='utf-8'))
    boundary = json.loads((OUT/'boundary.json').read_text(encoding='utf-8'))
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    counts = Counter(item[0] for item in trajectory())
    lines = [f'# 20-局部适用域判据与核显双精度扫掠实验报告\n',
        f'> 生成时间：{stamp}（北京时间）\n> 修改时间及内容：{stamp}，首次生成，记录局部判据消融、逐状态验收及核显实测。\n'
        '> 文档概述：对应v2工作一与工作二。检验远处高点造成的保守拒绝是否可解除，同时验证核显实际计算；不宣称完成实时系统或通用网格算法。\n',
        '## 索引目录\n\n1. 问题与数学依据\n2. 几何对照与独立验收\n3. 核显计算实验\n4. 复现与研究边界\n',
        '## 一、问题与数学依据\n',
        '本次假设：全维护域最高点C过度限制局部扫掠；替换为历史足迹超集上的原骨面上界，可以扩大适用范围而不改变质量门槛。'
        '这是一般判据改进，不读取失败面编号。初始骨面仍为经覆盖、投影无重叠及无遮挡验证的分片线性函数h₀。\n',
        '对水平等高线段Sⱼ、球半径Rⱼ和球心高度zⱼ，令dⱼ(x)=dist(x,Sⱼ)。在dⱼ≤Rⱼ内，扫掠下表面为'
        'gⱼ(x)=zⱼ−√(Rⱼ²−dⱼ(x)²)，当前目标高度为原面与所有有效下表面的最小值。'
        '局部高度图仅适用于原面低于相交球的球心；不能将这一公式直接用于倒扣或球体内部之外的上侧表面。\n',
        '令Bⱼ为胶囊XY足迹的轴对齐包围矩形。每个原始三角面与Bⱼ裁剪，仿射高度在裁剪多边形顶点取得最大值，'
        '得到Cⱼ；取C*=maxⱼCⱼ。因为真实足迹包含于矩形，h₀在所有历史足迹上均≤C*。要求所有历史工具满足δⱼ=zⱼ−C*>0，'
        '不能只检验最新工具。活动切削点满足gⱼ≤h₀≤C*，因此dⱼ≤√max(0,Rⱼ²−δⱼ²)，'
        '并有坡度界Lⱼ≤√max(0,Rⱼ²−δⱼ²)/δⱼ。取L=max(L₀,Lⱼ)，沿用逐三角形证书'
        'E_T≤max格点|h−h_T|+(L+‖∇h_T‖)diam(T)/n。\n',
        '上述为实数模型下、已验证单值图域内的推导；实现是含浮点容差的数值验证，不是区间算术证明。'
        '矩形外扩1e-10 mm、上界另加1e-9 mm；保留原高度查询容差预算。足迹联合上界仍可能偏保守，'
        '尚非逐面局部L或动态扩域。所有新面/过渡面逐次要求q≥0.4、最小角≥25°、垂直几何误差证书≤0.1 mm，'
        '固定边界、整骨水密/绕序/欧拉数及自交复核均不省略。不合格即拒绝，不保证任意输入都能继续。\n',
        '## 二、几何对照与独立验收\n',
        '共享19号合格初始整骨、4823个维护三角面、同一16段交叉轨迹、R=3 mm及相同验收参数。'
        '唯一变量为全域/历史足迹上界。每条序列首拒绝即停止，后续未执行不计成功；z是球心高度而非去除深度。\n',
        '| 判据 | z/mm | 接受/计划 | 实际变化步 | 最大去除/mm | 最小角/° | 最大证书/mm | 请求耗时均值/P95/P99/最大 ms |\n|---|---:|---:|---:|---:|---:|---:|---|']
    for run in comparison['runs']:
        accepted = [r for r in run['records'] if r['accepted']]
        angle = min((r['min_angle_deg'] for r in accepted), default=float('nan'))
        bound = max((r['error_bound_mm'] for r in accepted), default=float('nan'))
        lines.append(f"| {run['method']} | {run['z']} | {run['accepted']}/16 | {run['changed']} | {run['max_removal_mm']:.6f} | {angle:.6f} | {bound:.6f} | {stats([r['total_ms'] for r in run['records']])} |")
    lines += ['\n浅磨与中等深度两种判据得到相同最终几何；局部判据最后C*=0.285347264 mm，小于全域2.261836061 mm。'
        'z=1.8由全域首步拒绝变为局部16步接受，最大去除约1.198 mm；z=0仍首步拒绝。'
        '这仅扩大一档受限局部深度，不代表深台阶或原手术计划已支持。\n',
        f"真实边界负例：{boundary['record']['reason']}；几何、工具历史、全域上界恢复检查通过。\n",
        '保存状态全部重读检查q/角/退化、XY固定、外部原顶点不变。每个末态面积加权采样10000点，'
        '种子20260907，以独立原骨面射线查询及扫掠公式对拍；采样误差逐点小于所在面证书。'
        '拒绝配置的末态是初始面，不能当作完成磨削的误差结果。\n',
        '| 判据 | z | 保存状态 | 采样均值/P95/P99/最大误差 mm |\n|---|---:|---:|---|']
    for row in audit:
        values = '/'.join(f'{row[k]:.6f}' for k in ('mean_mm', 'p95_mm', 'p99_mm', 'max_mm'))
        lines.append(f"| {row['method']} | {row['z']} | {row['states']} | {values} |")
    lines += ['\n几何耗时只包含更新及整骨复核，不含初始化、文件导出、状态字段或渲染。按固定次序各跑一次，'
        '首条序列短时与探索GPU并行，故本表只用于负载描述，不作为严谨性能加速比；逐状态记录包含嵌套height/certificate计时，不能直接相加。\n',
        '## 三、核显计算实验\n',
        f"实测设备：{gpu['device']}；驱动{gpu['driver']}；{gpu['opencl']}；PyOpenCL {gpu['pyopencl']}。"
        '使用实际GPU设备、double输入/计算/输出，OpenCL CL1.2编译选项，不启用fast-math，关闭浮点合约。'
        '核显共享内存，设备名16GB不是独显显存证据。此结果不证明原生硬件FP64吞吐架构。\n',
        '相同16工具、平面零初始高度、种子20260907；3轮预热、10轮测量，CPU/GPU交替先后，复用已分配缓冲区。'
        'GPU主机墙钟包含每轮XY/初始高度/工具上传、核执行、下载与同步；不含分配、编译、原骨面高度查询。'
        '正式GPU单独复测在几何实验结束后进行，首轮并行探索保存在gpu_parallel_exploratory.json。CPU为NumPy向量化参照，'
        '不是优化过的多线程C++竞争基线，不得将该加速比解释为硬件能力比或完整系统收益。\n',
        '| 查询点数 | CPU中位ms | GPU墙钟中位ms | 核中位ms | 传输中位ms | CPU/GPU墙钟比 | 最大数值差/mm |\n|---:|---:|---:|---:|---:|---:|---:|']
    for run in gpu['runs']:
        m = run['medians_ms']
        lines.append(f"| {run['points']} | {m['cpu_ms']:.4f} | {m['gpu_wall_ms']:.4f} | {m['kernel_ms']:.4f} | {m['transfer_ms']:.4f} | {m['cpu_ms']/m['gpu_wall_ms']:.2f} | {run['max_abs_error_mm']:.3e} |")
    lines += ['\n补充尾部统计：每项顺序为均值/P95/P99/最大，单位ms；10次的P99仅描述本批样本，不是稳定尾部估计。\n']
    for run in gpu['runs']:
        lines.append(f"- N={run['points']}：CPU {stats([r['cpu_ms'] for r in run['timings']])}；GPU墙钟 {stats([r['gpu_wall_ms'] for r in run['timings']])}；GPU墙钟>100ms比例 {np.mean([r['gpu_wall_ms']>100 for r in run['timings']]):.0%}。")
    lines += [f"\n驻点、球面边界、域外、近边界共{gpu['analytic_cases']}个解析期望点（含重复扫掠）通过，最大误差{gpu['analytic_max_error_mm']:.3e} mm。"
        '随机对拍容差1e-10 mm是数值一致性标准，不是新几何误差证明。未接入在线几何证书或GUI，未验证系统实时性。\n',
        'API依据为官方文档（实现接口依据，非算法论文）：[程序与内核](https://documen.tician.de/pyopencl/runtime_program.html)、'
        '[队列与事件计时](https://documen.tician.de/pyopencl/runtime_queue.html)。\n',
        '## 四、复现与研究边界\n',
        f"原计划静态阶段计数：{dict(counts)}，总计{sum(counts.values())}。本次没有执行该138步计划。"
        '面粗/面精是水平扫掠但覆盖范围不同，仍需扩域与逐步验证；台粗/台精的球心低于当前图域高度上界；'
        '柱钻有垂直位移，不符合当前Sweep定义。不能跳过这些段后报告全轨迹完成。\n',
        '本次全域/局部是机制消融，CPU/OpenCL是同公式实现对比，均不替代已有算法竞争实验。'
        '19号Triangle构网对照仅提供构网基础；连续布尔及布尔后重网格的同轨迹、同精度公平比较仍必须补齐，'
        '才能评价学术贡献，不能据此宣称优于已有算法。\n',
        '复现：在项目根目录执行以下命令；几何实验与GPU性能实验应串行。实验结果保存在本实验目录/实验结果，源面不覆盖。\n',
        '```powershell\nuv pip install --python .\\.venv\\Scripts\\python.exe -r .\\初步实验\\局部适用域与核显计算\\requirements.txt\n'
        '.\\.venv\\Scripts\\python.exe -m unittest discover -s 初步实验\\局部适用域与核显计算 -p test*.py\n'
        '.\\.venv\\Scripts\\python.exe 初步实验\\局部适用域与核显计算\\experiment.py\n'
        '.\\.venv\\Scripts\\python.exe 初步实验\\局部适用域与核显计算\\gpu_experiment.py\n'
        '.\\.venv\\Scripts\\python.exe 初步实验\\局部适用域与核显计算\\audit.py\n'
        '.\\.venv\\Scripts\\python.exe 初步实验\\局部适用域与核显计算\\boundary_check.py\n'
        '.\\.venv\\Scripts\\python.exe 初步实验\\局部适用域与核显计算\\report.py\n```\n',
        '依赖沿用项目.venv，仅新增PyOpenCL2026.1.4及其pytools2026.1.1、siphash24 1.8。无Conda/Docker/CUDA配置、无外部GPU租用。'
        '6项新单元测试及23项既有解析/投影/拼接/联合测试通过；另有真实边界拒绝、8组保存状态审计及GPU解析/随机对拍。\n',
        '下一步：将核显扫掠接入真实原骨面高度查询后的证书计算，做完整逐状态CPU/GPU同精度对照；'
        '同时以明确适用域管理推进更大范围面磨轨迹，补充独立骨面与竞争算法基线。'
        '不得取消质量验收换实时性，不得将固定XY提升等同于任意曲面动态重三角化。\n',
        '代码审查按karpathy-guidelines控制改动范围，并按code-review-and-quality检查异常状态恢复、外部原面保护、GPU设备筛选及计时口径。'
        '本轮保留独立实验，不修改原演示入口；无合并或第三方源码修改。\n']
    hashes = {str(p.relative_to(PROJECT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [*ROOT.glob('*.py'), ROOT/'sweep.cl', ROOT/'requirements.txt',
                        ROOT.parent/'边界过渡带联合重建/dynamic.py', ROOT.parent/'边界过渡带联合重建/实验结果/joint.npz']}
    (OUT/'manifest.json').write_text(json.dumps(dict(time_bjt=stamp, sha256=hashes), ensure_ascii=False, indent=2), encoding='utf-8')
    path = PROJECT/'课题规划与专题调研/20-局部适用域判据与核显双精度扫掠实验报告.md'
    path.write_text('\n'.join(lines), encoding='utf-8')
    print(path)
