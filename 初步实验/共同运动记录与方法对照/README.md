# 共同运动记录与方法对照

本目录保存32号计划的共同仿真输入、解析材料状态、曲面方法对照和状态体积固定答案。所有坐标使用右手骨坐标系，长度为毫米，时间为毫秒。

## 复现

先运行不依赖Geogram二进制的局部测试：

```bash
../../.venv/bin/python -m unittest -v test_motion_record.py
../../.venv/bin/python -m unittest -v test_real_ct_state.py
../../.venv/bin/python screen_quality_failure_cases.py
../../.venv/bin/python real_ct_state.py
../../.venv/bin/python continuous_state_timeline.py
```

macOS Apple Silicon上首次运行正式Geogram对照前，恢复已登记的子模块并构建固定提交：

```bash
git submodule update --init --recursive reference/近期强基线_20260908/geogram
./初步实验/共同运动记录与方法对照/build_geogram_baseline.sh
```

随后运行完整实验：

```bash
../../.venv/bin/python experiment.py
```

`experiment.py`会在`实验结果/<北京时间>/`中保存`results.json`、候选网格、Geogram逐步输入输出和日志。当前最终本地证据目录为`实验结果/20260918_000123/`。

PaMO作者三阶段对照使用上述目录中四条挑战路线的最终Geogram闭合OBJ。固定参数为`ratio=1.0`、`min_vertices=0`，三个阶段全部开启。先生成带源码提交和输入摘要的远端包，再通过既有NVIDIA连接执行并回收结果：

```bash
../../.venv/bin/python prepare_pamo_remote.py 实验结果/20260918_000123
../../.venv/bin/python execute_pamo_remote.py \
  实验结果/20260918_000143_pamo_prepared
```

当前包摘要为`c4c72ae66010cffe0979e81c72a93980adccf6809dd1615ad477692569c61367`。执行器要求项目根目录`.env`提供既有`CUDA_SSH_HOST`、`CUDA_SSH_PORT`、`CUDA_SSH_USER`和`CUDA_SSH_PASSWORD`；当前该文件缺失，因此`remote_attempt.json`记录为连接配置阻塞，不能记作PaMO算法失败。

真实CT局部状态的当前证据为`实验结果/20260918_004101_real_ct_state/`。它复用既有公开肩胛骨、计划坐标、合格共边初态和16段仿真轨迹，在完整覆盖的6 mm半径圆盘上输出名义状态、逐面状态字段及三档保守误差区间。`ValidatedSession`只在网格验收通过后发布同一步状态，拒绝时保留上一状态；状态耗时计入`wall_ms`并单列`state_ms`。

持续输入时间线证据为`实验结果/20260918_005937_timeline/`。它重放一次本机Qt顺序执行耗时，在10 Hz、2 Hz、1 Hz合成输入下逐条计算全部16个运动事件，只在100 ms刷新时显示最新已完成合格状态；不得解释为真实线程调度或跟踪设备测试。

## 结果边界

- `analytic_height_source_fitted`只在原始候选质量失败单元内工作，通过单元不改动。
- `quality_failure_cases_v2.json`在来源修复运行前冻结，且用`0.025 mm`密集检查排除了内部空腔；四例原始候选均失败，固定来源规则仅一例完全通过。
- `quality_failure_cases.json`保留为筛选反例：只用`0.1 mm`网格检查适用域会漏掉两例内部空腔，不能作为正式泛化集。
- `geogram_exact_csg`是TOG 2025作者精确网格CSG的几何基线；工具仍是离散三角胶囊，未附加质量维护。
- PaMO固定作者提交`a10e34351eb7de71f41eb279e7ab9b2b101cf7a4`和AGPL-3.0许可证；本机无CUDA，远端结果返回前不得填写质量结论。
- 状态体积来自解析仿真材料场和固定求积，不是实际磨后骨量。
- `real_ct_uncertainty_scenarios_v2.json`中的非零误差值均为明确标注的仿真假设，不是设备规格或临床阈值；区间按绝对上界相加，不是概率置信区间。
- 真实CT局部状态只覆盖半径6 mm，不含完整12.5 mm计划边界，因此不评价真实CT上的计划外去除。
- 当前没有真实运动、实测磨后骨量或CUDA端到端结果。
