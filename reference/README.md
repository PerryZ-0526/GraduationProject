# reference 目录说明

> 更新时间：2026-09-02 17:21:06（北京时间）

本目录存放课题精读文献对应的开源代码实现，供后续开源代码分析使用。

## 仓库清单

| 目录 | 对应文献 | 实现性质 | 说明 |
| --- | --- | --- | --- |
| RXMesh/ | Mahmoud, Porumbescu & Owens 2025《Dynamic Mesh Processing on the GPU》（ACM TOG / SIGGRAPH 2025，见 05 号精读文档） | **官方开源** | 完整动态网格处理系统：空腔算子（include/rxmesh/cavity_manager.cuh）、patch 调度器（patch_scheduler）、动态拓扑（rxmesh_dynamic.cu）、直方图优先队列等。仓库地址：github.com/owensgroup/RXMesh，克隆方式 git clone --depth 1 |
| hypercut/ | Nehring-Wirxel, Trettner & Kobbelt 2021《Fast Exact Booleans for Iterated CSG using Octree-Embedded BSPs》（Computer-Aided Design，见 07 号精读文档） | **第三方实现**（quadmotor/hypercut，C++20，2024 年更新） | 仅实现 BSP 树部分（src/bsp），**限 128 位算术**（对应论文 0.22 mm 坐标分辨率，低于课题 0.1 mm 精度目标，用于基线时须核对）。含 --mill 铣削仿真入口。原论文无官方代码 |
| InteractiveAndRobustMeshBooleans/ | Cherchi, Pellacini, Attene & Livesu 2022《Interactive and Robust Mesh Booleans》（ACM TOG / SIGGRAPH Asia 2022，见 `课题规划与专题调研/02-三大研究工作文献调研报告.md` #2） | **官方开源** | 交互式鲁棒布尔，242 stars（2026-09 核对）。最接近"增量布尔"的带码参照，可作工作一的对拍实现 |
| OpenMeshCraft/ | Guo & Fu 2024《Exact and Efficient Intersection Resolution for Mesh Arrangements》（ACM TOG / SIGGRAPH Asia 2024，见 `课题规划与专题调研/02-三大研究工作文献调研报告.md` #3） | **官方开源** | 交点精确求解在 src/OpenMeshCraft/Arrangements，入口 test/Executables/arrangements.cpp。支撑近重合/退化求交的鲁棒处理 |
| meshtaichi/ | Fang, Liu, Zhang et al. 2022《MeshTaichi: A Compiler for Efficient Mesh-based Operations》（ACM TOG / SIGGRAPH Asia 2022，见 `课题规划与专题调研/02-三大研究工作文献调研报告.md` #6） | **官方开源** | 网格编译器，已并入 Taichi 主线（pip 安装 taichi + meshtaichi_patcher），本目录为示例仓库。工作二 CPU/GPU 通用后端参照 |

## 未能获取的代码

- Schmidt & Brochu 2016《Adaptive Mesh Booleans》（见 06 号精读文档）：算法实现在 Autodesk Meshmixer 中，但其源码仓库（github.com/meshmixer/MMX）已下线（404），组织下仅剩 API 文档仓库 mm-api，且未找到可用 fork。如需分析其算法，可参考论文伪代码 + HyperCutter 的重网格实现思路。

## 使用提示

- 两仓库均为浅克隆（--depth 1），如需完整提交历史可重新克隆。
- RXMesh 依赖 CUDA 12.x 与支持共享内存动态并行的 NVIDIA GPU（论文实验平台为 RTX 4090）；构建方式见其 README.md 与 CMakeLists.txt。
- hypercut 依赖 Eigen 3.4（third_party/ 内已含），CMake 构建。
- 代码分析优先级建议（对应课题）：RXMesh 的 cavity_manager / patch_scheduler / lp_hashtable（ribbon 哈希）为核心分析对象；hypercut 的 src/bsp 为迭代布尔参考实现。
