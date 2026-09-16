# 01-RXMesh远端构建障碍与强对照接入方案

> **生成时间**：2026-09-08 14:21:03（北京时间）
> **修改时间及修改内容**：2026-09-08 14:21:03，首次生成，记录作者源码核对、远端配置失败、真实整骨输入检查与后续接入建议。
> **修改时间及修改内容**：2026-09-08 14:26:02，用户追加授权在隔离venv安装固定cmake3.31.6、允许隔离依赖下载；实际安装请求、只读重试及恢复脚本上传共三次SSH建连失败，未执行远端安装。新增分阶段恢复入口，当前阻碍更新为连接不可用。
> **文档概述**：对应研究一的质量维护强对照和研究二的CUDA动态拓扑验证。已读取AGENTS.md、研究内容.md、18号规划及karpathy-guidelines。仅本目录及远端对应隔离目录产生新增文件；未修改上游、其他实验、根规划或界面，未安装依赖。当前结论为配置受阻，非GPU算法运行失败，更非质量维护成功。

## 索引目录

1. 已执行结果与证据
2. RXMesh源码入口及构建依赖
3. 最小真实整骨实验与输出适配
4. PaMO入口、依赖与适用范围
5. 公平性与不能保证的事项
6. 复现命令和交接

## 一、已执行结果与证据

**最新状态**：用户已授权隔离venv安装`cmake==3.31.6`，不再受安装权限限制。但原先可用SSH连接随后连续三次返回`NoValidConnectionsError`，均在执行远端命令前失败；未知是否实例或SSH服务状态变化。未创建新venv或安装CMake，未进入编译。最新完整脱敏记录见`实验结果/20260908_142602_setup/0.log`及`record.json`。下文CMake配置失败为连接失效前的实际历史证据，不能把二者混为同一次运行。

远端实际执行一次作者CMake配置，退出码1：

```text
CMake Error at CMakeLists.txt:3 (cmake_minimum_required):
  CMake 3.25 or higher is required. You are running version 3.22.1
```

尚未编译、链接或启动Remesh；没有GPU动态操作成功证据、输出OBJ或运行质量数据。GPU枚举成功仅说明设备可见。检查常用目录未找到备用CMake，不据此声称整个服务器不存在任何其他安装。

硬件/工具实测：RTX 4080 SUPER、驱动580.105.08、计算能力8.9、上报32760 MiB；CUDA Toolkit12.8.93、GCC11.4.0、CMake3.22.1。上报显存不用于推断零售硬件规格。

远端隔离目录：`/root/autodl-tmp/graduation_project/build_rxmesh_dynamic_20260908_141858`。一次配置失败后只检查已有替代工具，未升级工具链或重复无效编译。

本地证据：

- `实验结果/20260908_141858/01_environment.log`：真实环境输出。
- `实验结果/20260908_141858/05_configure.log`：实际失败原文。
- `实验结果/20260908_141858/06_alternative_cmake.log`：限定目录搜索无输出。
- `实验结果/20260908_141858/manifest.json`：完整命令、返回码、上游提交、每个白名单文件SHA256与大小。
- `实验结果/20260908_141858/rxmesh_source.tar.gz`：291个文件、未压缩2739633字节；仅作者构建脚本、库源码、应用、许可证和cloth输入，无.git、.env或项目凭据。
- 源码包SHA256：`b43da5b79176be1dbf0562b7f426caa6fce71ffeefc4118906e697b8cab3279c`，上传后远端sha256sum一致。
- `输入核对.json`：用户指定两份真实整骨输入的本地只读检查。未上传或运行这两个输入；源码包cloth亦未运行。
- `result.json`：供主线程读取的当前状态，`status=connection_failed`、`previous_status=configure_failed`、`output_obj=null`、`accepted=null`。空值表示未执行，不能显示成质量拒绝或通过。

## 二、RXMesh源码入口及构建依赖

本节路径均相对于项目根目录；仓库前缀为`reference/近期强基线_20260908/RXMesh/`。

上游提交：`e468c34ffabc70cd207309bce662d4821a9ed3b7`；检查前后工作区均无修改。顶层LICENSE是BSD-2-Clause。22号将其登记为2025 TOG动态网格论文作者库；本次验证的是此快照，不代表精确复现论文发表时版本。

|入口|源码核对结果|
|---|---|
|`apps/Remesh/remesh.cu`|作者CLI；`-i`输入OBJ，`-o`报告目录，`-n`迭代数，`--relative_len`相对平均边长，`-d`设备。构建RXMeshDynamic后显式拒绝非edge-manifold输入。|
|`apps/Remesh/remesh_rxmesh.cuh`|操作顺序为split、collapse、valence flip、tangential smoothing；默认3轮、每轮5次平滑。目标边长为输入平均边长乘relative_len，长/短阈值为4/3与4/5。保存JSON，末尾validate和OBJ导出被注释。|
|`apps/Remesh/split.cuh`、`collapse.cuh`、`flip.cuh`|真实CUDA拓扑内核，调用CavityManager、cleanup、slice_patches；不能由顶点移动代替这几类动态操作验证。|
|`apps/Remesh/smoothing.cuh`|投影到当前顶点局部切平面的松弛，不是投影回原始骨面、累计扫掠或解析目标边界。|
|`apps/Remesh/CMakeLists.txt`|目标名Remesh；链接RXMesh、CLI11、OpenMeshCore、OpenMeshTools。|
|`cmake/RXMeshApp.cmake`|为库与应用启用CUDA device LTO及`-use_fast_math`。|
|`cmake/ThirdParty.cmake`及各依赖cmake|通过FetchContent获取多个依赖；克隆主库不代表依赖已具备。|
|`include/rxmesh/rxmesh_static.inl`|`export_obj`使用30位文本精度，但中间容器是`glm::vec3`，不能据文本位数宣称double无损导出。|

实际工具要求比顶层最低版本声明更严格：顶层无条件设置CMP0169，该策略由CMake3.30加入。因此不修改上游时，应提供兼容的CMake3.30.x等版本，单纯换成3.25仍不够；未验证所有更高版本都兼容。依据为源码及[CMake官方CMP0169说明](https://cmake.org/cmake/help/latest/policy/CMP0169.html)，联网核验日期2026-09-08。

依赖清单：C/C++17与CUDA17工具链、CUDA runtime/cuSPARSE/cuSOLVER、OpenMP，以及OpenMesh8.1、CLI11 v2.3.2、rapidobj v1.1、rapidjson固定提交、spdlog v1.8.5、GLM1.0.1对应提交、cereal v1.3.2、cuBQL main、METIS固定提交、Eigen固定提交、CPM0.39.0。具体URL和提交见对应cmake。cuBQL使用浮动main，成功配置后必须另存其实际SHA。Polyscope、cuDSS、SuiteSparse可关闭；关闭Polyscope仍需上述核心依赖。

后续风险是OpenMesh的RWTH `:9000` Git源、Eigen GitLab、GitHub依赖下载及版本兼容。它们本轮尚未尝试，不标为已失败。不要直接执行全部依赖安装或替换系统库；可用时只在隔离build内构建所需目标。

注意`cmake/GitVersion.cmake`会在源码副本下生成未跟踪的`include/rxmesh/util/git_sha1.cpp`。未来只能对隔离build内的可丢弃副本配置，保留原始tar与摘要，不能对本地reference或共享源码配置；无.git副本的内置版本字段不可靠，应以外置manifest提交SHA为准。本轮在版本检查处退出，尚未生成该文件。

## 三、最小真实整骨实验与输出适配

研究假设：作者局部拓扑操作能否在既有真实整骨与磨削后候选上运行，并在相同外部质量指标下改善三角形形状。可证伪判据：失败、超时、无实际拓扑变化、几何漂移超预算或质量不合格均记录；不预设作者方法满足本项目门槛。

用户指定输入位于`初步实验/CUDA真实骨面对照/强基线覆盖结果/20260908_132411/`，保持原始mm坐标、不归一化、不预修复：

|输入|顶点/面|全骨q最小值|全骨最小角|q<0.4面数|角<25°面数|
|---|---|---|---|---|---|
|`initial.obj`|22349 / 44694|0.0000569176|0.00188282°|2009|8346|
|`raw_2.obj`|22514 / 45024|0.0000569176|0.00188282°|2243|8620|

两者边计数水密、绕序一致、欧拉数2、零面积面0。这些不证明无自交或顶点流形。float转换最大顶点位移均约0.00000542219 mm，只是I/O量化，不含后续算法误差。

这些是全骨既有差面统计，不能误称此前局部重建验收失败。全骨Remesh修改范围更大，必须分别说明全骨质量与原研究局部质量门槛的评估范围。

恢复构建后的最小顺序：

1. 以作者默认float/fast-math模式，只构建`Remesh`目标。先对`initial.obj`执行`-n 1 --relative_len 1.0 -d 0`，输出到独立`initial_n1`；再对`raw_2.obj`同参数运行。初次运行不作为预热后的性能结论。
2. 作者CLI不写OBJ。新增独立`remesh_export.cu`适配入口（当前尚未编写/编译），持有坐标双缓冲并调用原split/collapse/flip/smoothing函数，保持作者默认顺序、阈值和5次平滑；只增加计数、拓扑验证、同步、导出与JSON，不修改作者内核。需先与原CLI同输入做结果核对，不把适配直接称为论文原版。
3. 每轮平滑后原编排有坐标指针交换；不能在调用结束后直接导出`get_input_vertex_coordinates()`而假定它永远是最终状态。独立入口须持有最终活动坐标指针，再执行`update_host()`、DEVICE→HOST及`export_obj`。float模式可以使用作者导出；将来double模式需独立无float中转的导出器。
4. 先保留输入与输出顶点/面/连接摘要、CUDA同步返回码及split/collapse/flip阶段计时；顶点/面数改变能证明拓扑变化，但不分别证明每一种操作都成功，分别验证需操作计数或逐阶段连接摘要。同步成功且运行了算子也不等于质量通过。
5. 外部验收输出：最小角、q、退化、边/顶点流形、水密、自交、绕序，以及对固定输入/独立几何真值的双向距离。采样误差记录均值、P95/P99和最大值，不命名为Hausdorff严格上界或证书。先做全骨单次维护，再考虑布尔后的连续回灌。

建议构建命令（未成功执行到build）：在兼容CMake下使用本次manifest内configure命令，然后`cmake --build build --target Remesh -j 4`。仅目标Remesh编译；根apps仍会配置其他应用，若出现无关应用依赖问题，可在本实验新建外层CMake，设RX_BUILD_APPS=OFF后单独add_subdirectory作者Remesh，避免改上游apps列表。

建议运行命令形态：`build/bin/Remesh -i <initial.obj绝对路径> -o <隔离输出目录> -n 1 --relative_len 1.0 -d 0`。输出目录先创建，运行加有限timeout；程序实际位置以构建结果为准。该命令只产生作者JSON，OBJ依赖上述独立适配。

## 四、PaMO入口、依赖与适用范围

仓库前缀`reference/近期强基线_20260908/pamo/`；提交`a10e34351eb7de71f41eb279e7ab9b2b101cf7a4`，工作区无修改；顶层AGPL-3.0。22号记录其为2025 CGF作者库，本轮只核对本地文档源码，未远端构建或安装PaMO。

- `example.py`：真实CLI入口，载入OBJ，转torch float32 CUDA顶点与int面，调用PaMO后导出OBJ。默认ratio实际为0.1，与README部分默认示例描述不同，应显式传参。
- `simp_cuda/pamo/__init__.py`：PaMO三阶段编排。Stage1使用cumesh2sdf与DMC，Stage2调用`_C.CUDSP_Free`，Stage3使用safe projection。Stage1分辨率按目标面数选256/128/64，存在归一化与表面偏移，不是固定mm误差预算。
- `simp_cuda/src/cusimp_free.cu`：float顶点、QEM相关代价、BVH及自交检查的CUDA简化；`src/bvh/`有相交判定代码。源码中有这些检查不等于本轮验证了论文保证或任意输入都安全。
- `simp_cuda/setup.py`：PyTorch CUDAExtension构建，默认`-O3 --extended-lambda --fmad=false`；需要匹配PyTorch/CUDA/编译器与Python ABI。
- `setup.sh`：安装cumesh2sdf、pdmc、CUDA扩展、再编译`safe_project/warp_`并安装safe_project；此脚本有实际安装动作，本轮未执行。
- `env.yaml`：作者Python3.10.13、NumPy1.26.4、libigl2.5.1、trimesh4.4.0等；torch未锁定版本。远端现有Python3.12环境不是作者已验证环境，不能视为无需适配。
- `simp_cuda/safe_project/setup.py`：NumPy、SciPy、trimesh、libigl；Warp子模块及相关源码构建另计。

关键接入陷阱：禁用stage1/stage3并不能免除它们的导入依赖，`__init__.py`顶层仍导入pdmc、pamo_safe_project、torchcumesh2sdf，构造时仍实例化DMC。直接API必须显式`min_verts=0`，否则该版本默认10000000000进入target_faces计算，提前停止含义不符合常规ratio期待；变量名虽为min_verts，代码实际与目标面数取max，应按实现记录。

最小后续方案：依赖齐备后以同一`initial.obj`和`raw_2.obj`运行example.py，显式ratio、min-vertex及阶段开关；先完整三阶段，再把禁stage1/禁stage3列为消融。完整PaMO是全局重网格/简化/安全投影参照，不是无需适配的局部每帧磨削器。依赖不齐时，不通过关闭开关宣称完成轻量PaMO复现。

## 五、公平性与不能保证的事项

RXMesh Remesh的明确能力是GPU网格拓扑修改与各向同性边长/价数调整；其边界保护会跳过涉及边界顶点的操作，可能无法修复边界附近差面。闭合骨面中的磨削交线不是拓扑边界，作者入口未提供该交线锁定/解析目标投影。它不是布尔差集、扫掠求解或质量证书算法。

不保证：逐面角≥25°、q≥0.4、误差≤0.1 mm、全局无自交、原始特征/体积保持、累计无漂移、任意非流形输入、原138段完成或100 ms实时。失败日志不能用于宣称本方法优于作者算法。

精度必须分层：作者RXMesh默认float并启用fast-math；RX_USE_DOUBLE仅影响输入坐标类型，而Remesh内部Stats、newCoords和compute_stats存在float硬编码，不能靠开关就声称完整double运行。PaMO也主要float32，禁止将它们与项目double表述为同精度。首先按作者模式与统一外部质量指标对照，披露精度差异；同算法CPU/GPU同精度实验应另设，不能以PaMO/RXMesh对不同CPU算法替代。

本次输入全骨已有差面，后续需区分既有未修改面与新生成面。全骨作者默认维护与局部方法的计算规模不同，首轮用于功能/质量诊断；公平性能实验需补足相同任务范围、传输、初始化、同步、质量检查和输出成本。GPU内核/作者JSON时间不等于端到端延迟。

## 六、复现命令和交接

本地实际命令：

```powershell
uv run --offline --no-project --with paramiko==5.0.0 python -B -X utf8 初步实验/RXMesh动态对照/probe_build.py
.venv/Scripts/python.exe -B -X utf8 初步实验/RXMesh动态对照/audit_inputs.py
```

前者使用已缓存Paramiko环境，未安装项目依赖；通过既有remote.py读取.env并连接，未输出凭据。每次会创建新隔离目录，适用于复现配置障碍，不是自动完成编译的脚本。后者读取两份原始OBJ，输出本目录输入核对JSON；未修改原始输入。

主线程可读取本目录`result.json`，所有相对路径以该文件目录解析。当前output_obj、quality_after和timing_ms为null；先展示配置受阻与原因。将来实际运行成功后再记录真实output_obj，accepted须经过质量验收才填true/false。不要用输入网格充当Remesh输出。

用户最新授权后新增`run_build.sh`与`resume_build.py`。前者固定隔离目录、北京时间、4线程，将临时文件/pip缓存也留在隔离目录；setup建立cmake_venv并固定安装3.31.6，configure使用该CMake与隔离FetchContent目录，build只编译Remesh。各阶段timeout分别180/360/480秒（setup的pip步骤限180秒）。脚本尚未成功上传，不能称已在远端验证。连接恢复后逐阶段运行：

```powershell
uv run --offline --no-project --with paramiko==5.0.0 python -B -X utf8 初步实验/RXMesh动态对照/resume_build.py setup
uv run --offline --no-project --with paramiko==5.0.0 python -B -X utf8 初步实验/RXMesh动态对照/resume_build.py configure
uv run --offline --no-project --with paramiko==5.0.0 python -B -X utf8 初步实验/RXMesh动态对照/resume_build.py build
```

每步成功后才能进入下一步。恢复脚本保存阶段日志和record.json，但不自动更新界面result.json，后续应根据实测更新；当前构建/连接状态和未执行OBJ适配必须继续明确。主线程更新AGENTS时可引用这些精确版本、命令及实际成功/失败状态，不能把授权等同于安装完成。

当前下一推进条件为恢复SSH连接；已获授权的工具链安装仍待执行。界面、研究内容.md、AGENTS.md和其他实验保持未修改，避免与主线程冲突。
