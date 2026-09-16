# 23-远程CUDA环境配置与首批实验报告

> **生成时间**：2026-09-08 11:57:00（北京时间）
> **修改时间及修改内容**：2026-09-08 11:57:00，首次生成：记录用户提供设备的连接、隔离环境、原生CUDA扫掠微基准与强基线准备。
> - 2026-09-08 11:59:00，补充Geogram系统TBB链接问题、作者示例及取回网格验收结果。
> **文档概述**：本轮属于v2工作二的CUDA计算验证，并启动工作一的Geogram强基线。首批结果仅覆盖受限解析扫掠查询，不含网格拓扑、几何误差证书或显示，不代表实时磨削完成。

## 索引目录

- 一、凭据与远程环境
- 二、实验假设与方法
- 三、实测结果
- 四、复现与证据
- 五、强基线与下一步

## 一、凭据与远程环境

用户已提供租用设备并授权连接、配置及实验。连接参数保存在根目录`.env`，不在报告中复制密码；新增`.gitignore`忽略`.env`及`.ssh_known_hosts`。Windows ACL已移除该凭据文件的继承授权，仅给当前用户显式完全控制。当前根目录没有Git仓库，忽略规则用于防止将来误提交；手动分享目录仍须排除凭据。

SSH首次连接采用TOFU记录主机指纹，后续密钥变化拒绝连接；首次指纹尚未由租赁控制台独立核对：`SHA256:liZ36vNCsNcNdXeWs4f+g5ZIhPM/ZihP834vxs8Ulqc`。凭据没有上传远端或写入运行日志。建议用户后续轮换已在对话中发送的密码。

|项目|实测配置|
|---|---|
|GPU设备名|NVIDIA GeForce RTX 4080 SUPER|
|显存|驱动报告32760 MiB；PyTorch可见32228 MB；按云实例上报记录，不推断标准零售规格|
|CUDA计算能力|8.9，80个SM|
|驱动|580.105.08；nvidia-smi显示CUDA兼容上限13.0，不等于安装Toolkit版本|
|Toolkit|12.8，nvcc V12.8.93，`/usr/local/cuda/bin/nvcc`|
|CPU|Xeon Platinum 8260；容器可见96逻辑CPU，cgroup配额12 CPU；实验使用4线程|
|预装Python栈|用户镜像Python3.12、PyTorch2.8.0+cu128、NumPy2.3.2；torch.cuda.is_available()为True|
|编译工具|GCC11.4.0、CMake3.22.1|
|工作目录|`/root/autodl-tmp/graduation_project`，所在数据盘50 GB|
|Python隔离环境|`/root/autodl-tmp/graduation_project/venv`，由预装Python以`--system-site-packages`创建，复用预装PyTorch，不是完全独立锁定镜像|

非交互SSH初始PATH缺少python/nvcc，使用显式路径解决；没有重装驱动、Toolkit或PyTorch。未创建额外租赁资源，未修改系统时区，实验脚本使用`TZ=Asia/Shanghai`。实例仍保留运行，不擅自关机或释放。

本机SSH脚本通过`uv run --no-project --with paramiko==5.0.0`使用临时工具环境，未修改项目`.venv`；依赖声明位于`初步实验/CUDA远程验证/requirements_remote.txt`。

## 二、实验假设与方法

研究问题：水平等高球心扫掠包络的独立查询能否在CUDA上与CPU双精度一致，传输是否抵消小规模加速？这是移植可行性试验，不宣称新算法贡献。

每段工具定义XY端点a、b，半径r与固定球心高度z。查询点p到线段的距离为d；若d≤r，则候选高度为`z-sqrt(r²-d²)`，所有段候选与原高度取最小值。距离单位mm。只适用于水平等高线段扫掠的下包络，不覆盖任意方向磨削或完整实体边界。

CPU与CUDA共用同一标量公式，均为double；CPU启用OpenMP4线程，CUDA每点一个线程、每块256线程、顺序遍历工具段。nvcc参数`-O3 -std=c++17 -arch=sm_89 --fmad=false -Xcompiler=-fopenmp,-ffp-contract=off`，不启用fast-math。

查询规模1024、16384、131072；轨迹段数16、138。输入为确定性XY格点与交错水平轨迹，显式包含中心/相切查询点。固定原高度3 mm、工具半径2 mm、球心高度1.8 mm。注意138表示本微基准构造的138条线段，**不是原始真实骨面138步计划**。

每组预热5次、正式20次，串行运行各配置；CPU计时与CUDA计时不重叠。CUDA事件测内核时间；主机墙钟测完整输入上传、内核执行、同步和结果下载。分配、编译、SSH、原面定位、网格质量验收、状态字段与显示均不在微基准计时内，因此不称其为系统端到端耗时。

程序先通过5个CPU解析点检查；各配置检查最终CPU/CUDA输出有限、最大差≤1e-10 mm、材料去除分类一致，否则非零退出。共用公式对拍不是独立几何真值证明；本次没有检验所有退化情形或建立浮点误差上界。

## 三、实测结果

运行标识`20260908_115336`。6组均通过，最大CPU/CUDA绝对差为0 mm，去除分类不一致数为0。该0仅代表本批双精度测试输出，不证明任意输入精确一致。

|查询点×段数|CPU均值ms|CUDA内核均值ms|含传输均值ms|含传输P95/P99/最大ms|均值加速比|
|---|---:|---:|---:|---|---:|
|1024×16|0.1060|0.0374|0.0745|0.0766 / 0.0773 / 0.0775|1.42|
|1024×138|0.3907|0.2874|0.3282|0.3339 / 0.3387 / 0.3398|1.19|
|16384×16|0.6230|0.0384|0.2085|0.2205 / 0.2241 / 0.2250|2.99|
|16384×138|4.5943|0.2895|0.4639|0.4667 / 0.4680 / 0.4684|9.90|
|131072×16|4.7572|0.2161|1.2878|1.3139 / 1.3642 / 1.3767|3.69|
|131072×138|37.9468|1.8139|3.0184|3.1136 / 3.3472 / 3.4056|12.57|

分位数采用NumPy线性插值。原始JSON保存三类全部20次耗时，可复算CPU和内核分位数；20次不足以可靠估计长期P99。120次含传输测量均未超过100 ms，但不能据此称磨削系统实时达标。小规模存在低于2倍的负面/弱收益证据，完整保留；未做跨进程重复、CPU线程数扫描或竞争算法性能排名。

## 四、复现与证据

本机入口：`初步实验/CUDA远程验证/remote.py`，凭据从根目录读取。使用示例：

```powershell
uv run --no-project --with paramiko==5.0.0 python -X utf8 初步实验/CUDA远程验证/remote.py --command 'nvidia-smi'
uv run --no-project --with paramiko==5.0.0 python -X utf8 初步实验/CUDA远程验证/remote.py --command 'bash /root/autodl-tmp/graduation_project/cuda_stage0/run_stage0.sh'
```

上传源码使用`--put 本地文件 远端文件`，取回证据使用`--get 远端文件 本地文件`；只传指定文件，不上传整个项目或.env。远端脚本按北京时间创建新结果目录。

本地原始结果：

- `初步实验/CUDA远程验证/sweep_20260908_115336.json`：全部原始计时与差异。
- `初步实验/CUDA远程验证/stage0_20260908_115336.tar.gz`：GPU/CPU信息、Toolkit、Python包清单与源文件/二进制SHA256。
- `初步实验/CUDA远程验证/sweep_benchmark.cu`、`run_stage0.sh`：实验源码及构建命令。

## 五、强基线与下一步

Geogram使用22号固定提交`130442ff0f0c069d48ab4ebb4012218f3d861cf2`对应本地源码及子模块打包上传，不从远端重新拉取漂移版本。包SHA256：`014f5835192e6640844cc72e433567f29b653d495dd31631993a9cc65cf3c67c`。未改第三方源码，无窗口Release构建，关闭Graphics/TetGen/Triangle，目标为当前快照实际存在的`geocsg`，不沿用先前猜测的`compute_CSG`入口。

构建脚本为`run_geogram.sh`，作者自带`example004`仅用于入口验收，不是骨科磨削比较。其最终运行结果追加于下方。

**实际运行结果**：首次构建在链接阶段缺少`tbb::detail::r1`符号。确认系统已有TBB后，通过CMake参数`-DCMAKE_CXX_STANDARD_LIBRARIES=-ltbb`显式链接，未改第三方源码。二次构建与`geocsg example004`退出码均为0，作者日志CSG总耗时0.055 s（单次示例，仅作诊断，不作性能基准）。结果取回为`初步实验/CUDA远程验证/geogram_example004.obj`，本机Trimesh载入后424顶点、864三角形，水密=True、绕序一致=True，体积2284.38181520961（作者示例坐标单位未视为临床mm）。未做自交、Hausdorff或逐面质量验收，不能宣称分析交付合格。

成功与首次失败日志分别为同目录`geogram_build.log`、`geogram_build_first_failure.log`。网格检查命令：

```powershell
& .venv/Scripts/python.exe -c "import trimesh; m=trimesh.load('初步实验/CUDA远程验证/geogram_example004.obj',force='mesh'); print(len(m.vertices),len(m.faces),m.is_watertight,m.is_winding_consistent,m.volume)"
```

后续优先：完成强基线真实输入适配、明确数学适用域与公平预算；再将CUDA算子接入实际原面查询、逐状态质量及误差管线。RXMesh/PaMO CUDA复现、原138步、动态拓扑与完整显示性能仍未完成，不能用此次微基准替代。硬件已经具备，不再把“本机缺卡”作为取消CUDA工作的理由。
