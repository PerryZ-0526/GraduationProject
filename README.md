# 骨表面增量重建与实时可视化

**换机接续入口**：[63号目标交接指南](课题规划与专题调研/63-连续磨削目标暂停与换机交接指南.md)及[64号Git与数据迁移指南](课题规划与专题调研/64-Git提交范围与实验数据集中迁移指南.md)。当前目标按用户要求暂停；未入Git实验数据按64号单独迁移，拉取仓库后仍需恢复这些资产和GPU环境。

面向机器人辅助反式肩关节置换中的肩胛盂磨削，研究三角骨面的增量重建、CPU/CUDA计算与一致性显示，以及剩余磨削量、过磨和不确定性表达。

本仓库是研究工作区，包含算法原型、实验数据、报告和第三方算法基线，不是临床软件。

## 研究主线

1. **几何约束下的骨面增量重建**：由初始骨面和累计球形磨钻扫掠定义目标几何，联合控制局部网格质量、误差和新旧区域边界。
2. **面向连续磨削的异构计算与一致性状态发布**：冻结研究一算法后，研究CPU/CUDA执行、连续输入调度、状态版本一致性及显示滞后。
3. **不确定性感知的磨削状态表达**：研究剩余量、完成度、过磨、越界及误差可信范围。

当前以第一项为主攻。完整定义见[研究内容.md](研究内容.md)，执行规范见[18-v2研究实验规划与学术验证规范](课题规划与专题调研/18-v2研究实验规划与学术验证规范.md)。

**后续Agent从这里开始**：[34-Geogram与PaMO组合优化研究方案及Agent执行指南](课题规划与专题调研/34-Geogram与PaMO组合优化研究方案及Agent执行指南.md)与[35号后续计划](课题规划与专题调研/35-Geogram与PaMO后续研究执行计划.md)。原版组合和开发批次已运行，当前按新版质量统计协议重审现有输出，再决定机制改进与连续验证。旧高度图和来源约束保留为受限对照。

## 当前状态

- Geogram已完成33号有限解析场景审计，可作几何参照；PaMO作者示例及原版组合已运行，六例在旧逐面质量协议下未通过。五种方法各21个开发输出的新版质量统计见[19号重审](初步实验/Geogram与PaMO组合验证/19-质量统计口径修订与开发输出重审.md)，12条独立路线和连续磨削尚未完成。
- 单个真实CT肩胛骨、固定局部图域和16段水平轨迹已完成逐状态重建与整骨验收。
- CPU在线窗口已接入，候选验收通过后才同步发布网格与刀位。
- 受限CUDA区间管线取得约2倍加速，但仍未达到100 ms目标。
- 竖直磨削已完成解析分层机制实验，尚未接入真实骨面。
- 原138段计划、一般三维动态重三角化、完整强基线竞争和不确定性评价尚未完成。

Geogram基线证据见[33号报告](课题规划与专题调研/33-Geogram精确CSG独立基线审计报告.md)，当前组合执行安排见34号和35号。此前阶段性对账保留在[阶段性汇报详细说明](阶段性汇报-915/02-阶段性汇报详细说明.md)和[阶段性汇报HTML](阶段性汇报-915/01-骨表面实时可视化阶段性汇报.html)。

## 快速开始

项目统一使用Python 3.13和[uv](https://docs.astral.sh/uv/)：

```bash
uv sync --extra opencl
uv run graduation-project info
uv run graduation-project test
uv run graduation-project gui
```

若不需要OpenCL探索环境：

```bash
uv sync
```

也可以激活环境后运行：

```bash
source .venv/bin/activate
graduation-project info
graduation-project test --suite core
graduation-project gui
```

Windows激活命令为：

```powershell
.\.venv\Scripts\Activate.ps1
```

## 统一命令

| 命令 | 作用 |
| --- | --- |
| `graduation-project info` | 显示项目根目录、解释器和核心依赖版本 |
| `graduation-project test` | 运行不依赖专用GPU的核心回归 |
| `graduation-project test --suite gui` | 运行真实Qt/VTK在线窗口回归 |
| `graduation-project test --suite opencl` | 运行Intel FP64 OpenCL回归，不满足硬件条件时跳过 |
| `graduation-project test --suite cuda` | 运行CUDA回归，不满足硬件条件时跳过 |
| `graduation-project test --suite all` | 运行核心与GUI回归，并自动探测可用硬件 |
| `graduation-project gui` | 启动默认受限在线重建窗口 |
| `graduation-project gui --legacy-bool` | 启动旧布尔演示，不保证逐状态网格质量 |

测试入口按实验目录逐个启动独立Python进程，避免同名模块、全局路径和原生库相互污染。

## 依赖分组

依赖统一定义在[pyproject.toml](pyproject.toml)，精确解析结果记录在`uv.lock`。

- 默认依赖：CPU几何、质量验收、Qt/PyVista界面和报告生成。
- `opencl`：PyOpenCL探索后端；现有实现要求唯一Intel双精度GPU。
- `remote`：远程CUDA实验所需Paramiko。
- `cuda`：Linux x86_64 NVIDIA环境使用的CuPy，不适用于Apple Silicon。

各实验目录中的旧`requirements*.txt`保留，用于复现历史报告；新环境优先以根级`pyproject.toml`为准。

## 目录结构

```text
.
├── src/graduation_project/       # 可安装命令行包与统一测试入口
├── 初步实验/                     # 算法、CPU/GPU实验、GUI和原始结果
├── 课题规划与专题调研/           # 研究决策、实验报告及34号Agent执行方案
├── 文献精读/                     # 临床、几何和GPU文献证据
├── reference/                    # 第三方算法Git submodule
├── 最小工作流验证/               # 早期合成场景CPU基线
├── 阶段性汇报-915/               # 最新汇报、阅读版和素材
├── 研究内容.md                   # 当前三项研究的权威定义
├── pyproject.toml                # 统一依赖与可安装包配置
└── AGENTS.md                     # 研究、实验和协作约束
```

第三方基线默认不会随普通检出展开。需要分析或构建时执行：

```bash
git submodule update --init --recursive
```

这些仓库没有统一构建入口，且部分依赖CUDA；只初始化和构建当前实验需要的基线。

## 默认在线链路

```text
真实骨面与固定轨迹
  → 局部目标几何
  → 边界及过渡带联合更新
  → 几何、拓扑、退化和自交检查；记录质量分布
  → 接受并发布独立快照，或拒绝并回滚
  → Qt/PyVista显示同版本网格、刀位和指标
```

默认在线入口仍是历史逐面严格协议实现，只支持已验证的真实骨面、固定图域及16段水平交叉轨迹；尚未按当前统计质量协议改造，不可把旧入口的质量拒绝直接作为当前Geogram＋PaMO评价结论。完整138段裁剪、跨域和竖直磨削不能通过该窗口宣称已经支持。

## 可复用磨削测试资产

新增[测试资产与复用协议](初步实验/可复用磨削测试集/01-测试资产说明与复用协议.md)：35个合成几何体、140条固定仿真路线，已转换成2345个离散扫掠工具；另有BodyParts3D八个骨模型的人为测试尺度派生件、16条路线及224个工具。开发与保留评价按几何体划分，使用前核对清单摘要。公开图谱来自一个成人男性，不能视为独立患者队列；测试尺度不代表恢复了真实解剖毫米。

```powershell
.\.venv\Scripts\python.exe 初步实验\可复用磨削测试集\validate_feedback.py --root 初步实验\可复用磨削测试集\连续输入_v1
.\.venv\Scripts\python.exe 初步实验\可复用磨削测试集\validate_feedback.py --root 初步实验\可复用磨削测试集\公开骨面连续输入_v2_精确去重
```

## 平台说明

- macOS Apple Silicon：PyMeshLab自带Qt5，与PyQt6同进程会冲突；项目已将PyMeshLab自相交检测隔离到子进程。
- Intel OpenCL：只用于历史探索和正确性对照，不替代CUDA研究交付。
- CUDA：正式实验需要NVIDIA设备，并应记录驱动、Toolkit、精度、预热、同步和端到端耗时。

所有距离默认使用毫米。当前组合研究以最小角低于10°、5°、1°的面占比为质量主指标，另报最小角≥25°且`q≥0.4`的高质量面占比、总面数、绝对数量与面积占比；有限非退化的小角面不单独触发拒绝。`0.1 mm`是几何误差预算，拓扑、退化、几何与状态一致性分别审查；这些都不是临床安全阈值。
