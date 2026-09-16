# 22-高水平算法基线拉取清单与CUDA研究路线

> **生成时间**：2026-09-08 10:56:00（北京时间）
> **修改时间及修改内容**：2026-09-08 10:56:00，首次生成：记录论文等级、作者代码快照、有效PDF与下载失败项，明确CUDA正式路线。
> **文档概述**：本次是文献与参考实现准备，不是算法复现或性能实验。四个作者代码仓库已拉取，声明的Git子模块已递归初始化；三份PDF通过解析及首页渲染检查，RXMesh全文未成功下载。未修改原始参考仓库，未新增项目环境依赖。

## 索引目录

- 一、筛选口径与论文清单
- 二、代码快照与许可证
- 三、论文文件与校验
- 四、如何作为公平对照
- 五、CUDA路线与后续进入条件
- 六、实际核验与未完成项

## 一、筛选口径与论文清单

正式竞争论文满足CCF-A、CCF-B或SCI一区至少一项。本批通过CCF期刊等级筛选：TOG为A类，CGF为B类，依据[CCF官方计算机图形学与多媒体目录](https://www.ccf.org.cn/Academic_Evaluation/CGAndMT/)，核验日期2026-09-08。不将会议宣传名称直接替代期刊等级，不声称额外满足某一年度JCR或中科院一区。

|论文正式名称|发表信息及等级|作者代码|与课题的对应关系|
|---|---|---|---|
|Exact predicates, exact constructions and combinatorics for mesh CSG|[TOG 2025，DOI 10.1145/3744642](https://doi.org/10.1145/3744642)，CCF-A|[Geogram](https://github.com/BrunoLevy/geogram)|精确CSG与几何正确性竞争参照；不自动保证磨削后单元形状质量|
|Exact and Efficient Intersection Resolution for Mesh Arrangements|[TOG 2024，43(6)，165，14页](https://mangoleaves.github.io/projects/mesh-arrangements/)，CCF-A；DOI 10.1145/3687925|[OpenMeshCraft](https://github.com/mangoleaves/OpenMeshCraft)|交点解析与共细分参照，不等于完整质量维护磨削系统|
|Dynamic Mesh Processing on the GPU|[TOG 2025，44(4)，136，19页](https://doi.org/10.1145/3731162)，CCF-A|[RXMesh](https://github.com/owensgroup/RXMesh)|CUDA动态拓扑、局部更新和重网格参照；不能单独承担几何布尔真值|
|PaMO: Parallel Mesh Optimization for Intersection-Free Low-Poly Modeling on the GPU|[CGF 2025，44(7)，DOI 10.1111/cgf.70267](https://doi.org/10.1111/cgf.70267)，CCF-B|[PaMO](https://github.com/SarahWeiii/pamo)，[作者项目页](https://seonghunn.github.io/pamo/)|GPU无自交网格优化参照；主要任务含简化和重网格，不能直接宣称适合术中每步磨削|

这是第一批与当前几何主干直接相关的合格候选，不是穷尽所有近期论文，更不代表已经证明其在本任务中的优劣。2025年Fast Intersection-Free Remeshing的[作者页面](https://ltrbless.github.io/projects/Remesh/)尚未核实有效官方代码入口，暂不列入“论文与代码均可获取”的已交付项。

## 二、代码快照与许可证

统一放在[`reference/近期强基线_20260908/`](../reference/近期强基线_20260908/)，均为独立浅克隆。此次锁定的是当前作者仓库版本，不保证恰为论文实验提交；正式复现前应根据发布标签、历史或作者说明进一步核对。

|目录|分支|完整提交SHA|顶层许可证|
|---|---|---|---|
|geogram|main|`130442ff0f0c069d48ab4ebb4012218f3d861cf2`|BSD-3-Clause|
|OpenMeshCraft|mesh-arrangements|`2426961915583f21dcda919d1f33f861694079e8`|GPL-3.0文本，组件条款另查|
|RXMesh|main|`e468c34ffabc70cd207309bce662d4821a9ed3b7`|BSD-2-Clause|
|pamo|master|`a10e34351eb7de71f41eb279e7ab9b2b101cf7a4`|AGPL-3.0|

许可证只是顶层盘点，不替代依赖许可审查或法律意见；不得把全部代码都视作宽松许可。GeogramPlus未包含在本次拉取中。

OpenMeshCraft README所写`mesh_arrangements`在远端不存在；`git ls-remote --heads`核实论文分支为`mesh-arrangements`，已使用后者。这是拉取入口更正，未修改第三方源码。

Geogram递归子模块10项、OpenMeshCraft 5项、PaMO 1项均已初始化，`git submodule status --recursive`没有未初始化或错位前缀。具体版本由父仓库gitlink固定。PaMO的Warp子模块提交为`fd17b8594a2f95f500884ff3d87904d776750897`。RXMesh没有声明Git子模块，构建中的FetchContent等依赖尚未下载；“子模块齐全”不等于“离线构建环境齐全”。

旧`reference/RXMesh`有三处已有修改，本次没有覆盖或拉取更新；旧OpenMeshCraft同样未改动。新四仓库工作区检查无修改。

## 三、论文文件与校验

有效文件保存于[`文献精读/近期强基线原文/`](../文献精读/近期强基线原文/)。原文保持原样，本文承担编号、时间与来源说明，不给作者PDF添加本项目封面。

|文件|来源与版本|页数|SHA256|
|---|---|---|---|
|01-精确网格CSG-作者预印本.pdf|[arXiv 2405.12949](https://arxiv.org/pdf/2405.12949)，首页v2，2025-06-04；正式TOG发表年份为2025|28|`f5a571dc59acfa9847719dd507d8215623e6cec06c73172fbecb29dba1c5f235`|
|02-网格交点精确解析-作者全文.pdf|[作者PDF](https://mangoleaves.github.io/files/2024-mesh-arrangements/MeshArrangements.pdf)，首页TOG43(6)，2024|14|`06282710dcb27d52aa01d1496ac02355ed13cc62705e286387783f9a6ded81a1`|
|04-PaMO无自交网格优化-作者预印本.pdf|[arXiv 2509.05595](https://arxiv.org/pdf/2509.05595)，首页v1，2025-09-06，含CGF44(7)排版|19|`d04c298238c0254af6d7eaaf1274497b98b672f85aa9a6db66d262b8316c5b9e`|

**03号RXMesh全文尚缺。** [作者主页](https://ahdhn.github.io/)链接至[eScholarship](https://escholarship.org/uc/item/1sm051d2)，页面返回验证提示；直接PDF、CloudFront及另一收录条目返回空文件，ACM PDF请求连接异常。未绕过访问控制，未将摘要或空文件冒充全文。正式论文信息已由ACM及作者出版清单核对，不引用同名HOPC短摘要替代19页TOG论文。

PaMO出版社下载入口返回HTML而非PDF，已改用作者arXiv版本。异常响应移到`tmp/pdfs/强基线检查/`留证，不在论文目录中充数；没有删除原有资料。

## 四、如何作为公平对照

本节为实验规划，不是复现结果。

1. **几何层**：Geogram精确CSG、OpenMeshCraft交点解析与现有2022鲁棒布尔共同参与几何验证。统一物理轨迹及工具离散误差预算；解析真值与复杂场景独立参照分开。精确谓词不能消除工具表面离散误差。
2. **质量层**：对同一更新候选比较现有维护方案、适用的PaMO/RXMesh重网格操作和拟议方法。记录适配改动、几何漂移、最差单元、自交、拒绝率；无法满足在线输入约束时如实列为不适用，不人为拼装成所谓论文原算法。
3. **性能层**：在同一CUDA设备上比较局部更新、质量维护、误差计算与完整管线。不能以本机CPU对远端GPU的硬件差异直接宣称算法优势；远程传输、排队和本地显示开销单列。
4. **消融**：几何状态分离、边界/过渡带机制、局部化、调度与CUDA分别消融。论文主张必须能被实验否证；若强基线更好，调整方法假设，不降低验收要求。

## 五、CUDA路线与后续进入条件

CUDA是用户指定的正式研究实现路线，不再作为可选后端。当前Intel核显OpenCL结果保留为探索与CPU对拍证据，不计作CUDA交付。CPU继续作为独立正确性参照；不能仅安装Toolkit或调用GPU渲染就宣称完成。

当前可做：明确数学适用域、核验代码入口、准备统一轨迹与逐状态验收、构建CPU强基线。CUDA设备到位后：记录驱动/Toolkit/计算能力/显存、编译选项及依赖版本；先执行作者最小示例，再进行同精度对拍和端到端计时。不得预先声称CUDA必然满足100 ms目标，也不因本机缺卡取消该研究环节。

本次未安装CUDA或新建Conda/Docker，未配置远程连接或产生租卡费用。后续资源接入须取得具体设备与连接信息；Docker只组织环境，不能替代NVIDIA硬件。

## 六、实际核验与未完成项

已执行`git clone --depth 1`、论文分支核验、`git submodule update --init --recursive --depth 1`、`git rev-parse HEAD`、`git status --porcelain`和PDF下载。使用Codex捆绑Python的pypdf逐文件解析，pypdfium2渲染有效PDF首页并人工视检，标题与论文相符；首页预览保存在`tmp/pdfs/强基线检查/`。SHA256对下载的原始字节计算，未改动原文。

未完成：RXMesh全文本地下载、四种代码的编译及最小示例、论文精确实验提交对应核查、正式磨削竞争实验和CUDA计算交付。当前进展不能描述为“四篇已复现”，也不能据此声称本课题优于上述方法。
