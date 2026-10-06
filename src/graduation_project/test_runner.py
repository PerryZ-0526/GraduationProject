"""在隔离子进程中运行分散在各实验目录的回归测试。"""
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

from .project import find_project_root


@dataclass(frozen=True)
class TestCommand:
    name: str
    arguments: tuple[str, ...]
    cwd: str = "."


CORE_TESTS = (
    TestCommand("三维目标几何", ("初步实验/三维目标几何机制/test_target.py",)),
    TestCommand(
        "Geogram基线适配",
        ("初步实验/Geogram几何基线审计/test_geogram_audit.py",),
    ),
    TestCommand("竖直磨削分层", ("初步实验/竖直磨削曲面分层/test_axis.py",)),
    TestCommand("计划裁剪特征重建", ("初步实验/计划裁剪特征重建/test_clipped_patch.py",)),
    TestCommand("共同运动记录", ("初步实验/共同运动记录与方法对照/test_motion_record.py",)),
    # 局部维护必须保留外部面和边界，独立于本机是否有CUDA硬件。
    TestCommand("布尔局部维护边界", ("初步实验/Geogram与PaMO组合验证/test_locality_masks.py",)),
    # 局部失败只能扩域一次，再全量回退；三次失败保留上一发布版本。
    TestCommand("布尔局部维护回退", ("初步实验/Geogram与PaMO组合验证/test_locality_feedback.py",)),
    # 数值碎片清理必须同步来源，不能删掉仍有三个不同顶点的细面。
    TestCommand("布尔来源清理", ("初步实验/Geogram与PaMO组合验证/test_locality_cleanup.py",)),
    # 来源丢失只能唯一恢复，双匹配和错误已有标签必须拒绝。
    TestCommand("布尔来源恢复", ("初步实验/Geogram与PaMO组合验证/test_locality_provenance_recovery.py",)),
    # 新机制与可复用资产纳入统一CPU入口，远端连续实验仍单独登记。
    TestCommand("自适应接缝与回滚", ("初步实验/Geogram与PaMO组合验证/test_adaptive_seam.py",)),
    TestCommand("共面质量与固定边", ("初步实验/Geogram与PaMO组合验证/test_planar_quality.py",)),
    TestCommand("可复用磨削资产", ("初步实验/可复用磨削测试集/test_reusable_cases.py",)),
    TestCommand("共面区域与孔洞", ("初步实验/Geogram与PaMO组合验证/test_planar_patch.py",)),
    TestCommand("正面积输入诊断", ("初步实验/Geogram与PaMO组合验证/test_positive_area_input.py",)),
    TestCommand("精确共享接触复核", ("初步实验/Geogram与PaMO组合验证/test_exact_alarm_contact.py",)),
    TestCommand("共同来源保留与核对", ("初步实验/Geogram与PaMO组合验证/test_shared_sources.py",)),
    # 独立参照必须禁止未来工具泄漏，并在新刀恢复失败时清除旧缓存。
    TestCommand("独立参照重放范围", ("初步实验/Geogram与PaMO组合验证/test_reference_replay_prefix.py",)),
    TestCommand("独立参照恢复与缓存", ("初步实验/Geogram与PaMO组合验证/test_independent_reference_recovery.py",)),
    # 相邻极小面修复不能丢闭合性；冻结入口不能静默使用变更后的清单。
    TestCommand("相邻小面受约束折叠", ("初步实验/Geogram与PaMO组合验证/test_small_incident_collapse.py",)),
    TestCommand("同来源反向面抵消", ("初步实验/Geogram与PaMO组合验证/test_opposed_facet_cleanup.py",)),
    TestCommand("点三角形有理数参照", ("初步实验/Geogram与PaMO组合验证/test_pt_exact_reference.py",)),
    TestCommand("点三角形梯度参照", ("初步实验/Geogram与PaMO组合验证/test_pt_gradient_reference.py",)),
    # 续跑须保留完整失败分母；小特征扫描的边界歧义不能计作通过。
    TestCommand("精度断连续跑校验", ("初步实验/Geogram与PaMO组合验证/test_precision_resume.py",)),
    TestCommand("精度续跑记录合并", ("初步实验/Geogram与PaMO组合验证/test_precision_merge.py",)),
    TestCommand("小特征固定扫描", ("初步实验/Geogram与PaMO组合验证/test_feature_line_audit.py",)),
    # 曲面资产须实际接触；非凸工具邻域不能填平工具之间的间隙。
    TestCommand("弯曲体接触资产", ("初步实验/可复用磨削测试集/test_curved_contact_cases.py",)),
    TestCommand("非凸工具表面邻域", ("初步实验/Geogram与PaMO组合验证/test_tool_surface_band.py",)),
    # 精确审计只能绑定终态实际保存对象，不能把复用事件算成新输出。
    TestCommand("发布对象精确审计范围", ("初步实验/Geogram与PaMO组合验证/test_published_embedding_scope.py",)),
    # 已见CT故障保留非有限能量证据，不能以自由导数有限替代完整数值检查。
    TestCommand("CT浮点退化与能量故障", ("初步实验/可复用磨削测试集/test_ct_precision_regression.py",)),
    # 原始几何与FP32编码分别对拍，不能以高精度运算补回已丢失的坐标信息。
    TestCommand("边边有理数距离参照", ("初步实验/Geogram与PaMO组合验证/test_ee_exact_reference.py",)),
    TestCommand("固定接触坐标量化", ("初步实验/可复用磨削测试集/test_fixed_contact_quantization.py",)),
    # 完整异常接触和真实零距离控制绑定实际CUDA输出，不将诊断误记为发布。
    TestCommand("全部固定原几何CUDA证据", ("初步实验/可复用磨削测试集/test_all_fixed_geometry_regression.py",)),
    # 原固定接触分支不能修改动态核体；输入许可须绑定后端而非全局放宽面积门槛。
    TestCommand("固定接触核体保留", ("初步实验/Geogram与PaMO组合验证/test_preserved_collision_source.py",)),
    TestCommand("原固定几何输入条件", ("初步实验/Geogram与PaMO组合验证/test_preserved_input_repair.py",)),
    TestCommand("完整固定几何投影证据", ("初步实验/可复用磨削测试集/test_preserved_projection_regression.py",)),
    # 新反馈只对固定后端允许编码退化，仍需同一保存对象的完整嵌入证据。
    TestCommand("原固定几何反馈门控", ("初步实验/Geogram与PaMO组合验证/test_preserved_feedback_gate.py",)),
    # 终态复审必须拒绝缺失、失败或与实际保存对象不符的精确证据。
    TestCommand("原固定几何保存证据绑定", ("初步实验/Geogram与PaMO组合验证/test_preserved_saved_binding.py",)),
    # 两真实父反馈帧保留编码退化计数，不能将局部成功改称原138段完成。
    TestCommand("CT第六第七事件真实反馈", ("初步实验/可复用磨削测试集/test_ct_feedback_precision_cases.py",)),
    # 独立参照每步核查后才能作为下一父网格，新切削失败必须清除旧缓存。
    TestCommand("逐步独立参照恢复", ("初步实验/Geogram与PaMO组合验证/test_guarded_reference_recovery.py",)),
    # 冻结故障输入保留原负例，并核对十二工具实际重放的同文件完整证据。
    TestCommand("CT独立参照故障资产", ("初步实验/Geogram与PaMO组合验证/test_guarded_reference_assets.py",)),
    # 十二步实际对象与原工具前缀绑定，修复面不能借用其他文件的精确证据。
    TestCommand("CT逐步参照完整对象", ("初步实验/可复用磨削测试集/test_guarded_ct_prefix_assets.py",)),
    # 子路线复审需要完整事件和结束状态，不能改写整批运行状态。
    TestCommand("已完成子路线复审范围", ("初步实验/Geogram与PaMO组合验证/test_completed_preserved_route.py",)),
    # 两类冻结清单只核查本包文件，缺失、改写和冲突摘要不得冒充通过。
    TestCommand("冻结资产完整性", ("初步实验/可复用磨削测试集/test_asset_integrity.py",)),
    # 新固定点只有首次求导且坐标逐位未移动时才能扩展原几何锚点。
    TestCommand("首次追加固定锚点", ("初步实验/Geogram与PaMO组合验证/test_fixed_anchor_contract.py",)),
    # 锚点变更后完整能量要重算，模拟测试保留重算仍非有限的负结果。
    TestCommand("固定锚点完整能量重算", ("初步实验/Geogram与PaMO组合验证/test_anchored_energy_refresh.py",)),
    # 原失败、仅掩码失败和完整重算通过必须绑定同一实际投影前对象。
    TestCommand("CT追加固定锚点实际对照", ("初步实验/可复用磨削测试集/test_ct_added_anchor_regression.py",)),
    # 运行中锚点记录也要核对重算、身份及数量，不能冒充整批终态验收。
    TestCommand("已发布锚点记录一致性", ("初步实验/Geogram与PaMO组合验证/test_published_anchor_records.py",)),
    # 保存复审必须核对追加锚点坐标，同时保留原父链、原顶点和几何门控。
    TestCommand("新增锚点保存复审", ("初步实验/Geogram与PaMO组合验证/test_anchored_saved_source.py",)),
    TestCommand("物理面积私有判据", ("初步实验/Geogram与PaMO组合验证/test_physical_repair_diagnostic.py",)),
    TestCommand("物理面积反馈保护", ("初步实验/Geogram与PaMO组合验证/test_physical_feedback.py",)),
    TestCommand("物理清理顺序与实际CT回归", ("初步实验/Geogram与PaMO组合验证/test_ordered_physical_cleanup.py",)),
    TestCommand("清理四因素消融契约", ("初步实验/Geogram与PaMO组合验证/test_cleanup_order_ablation.py",)),
    TestCommand("小特征真实四方法入口", ("初步实验/Geogram与PaMO组合验证/test_ordered_features.py",)),
    TestCommand("当前四方法三轮完整配对", ("初步实验/Geogram与PaMO组合验证/test_ordered_pairs.py",)),
    TestCommand("独立参照清理顺序与数据来源", ("初步实验/Geogram与PaMO组合验证/test_ordered_reference.py",)),
    TestCommand("保留评价实际方法与完整分母冻结", ("初步实验/Geogram与PaMO组合验证/test_ordered_evaluation_freeze.py",)),
    TestCommand("共面生成原活动面限定", ("初步实验/Geogram与PaMO组合验证/test_planar_active_patch.py",)),
    TestCommand("活动面限定父反馈发布契约", ("初步实验/Geogram与PaMO组合验证/test_active_patch_feedback.py",)),
    TestCommand("活动面传播单改动消融证据", ("初步实验/Geogram与PaMO组合验证/test_active_scope_ablation.py",)),
    TestCommand("活动面局部三因素真实消融", ("初步实验/Geogram与PaMO组合验证/test_active_patch_ablation.py",)),
    TestCommand("解析长路线独立等值面补查", ("初步实验/Geogram与PaMO组合验证/test_analytic_long_reference.py",)),
    TestCommand("清理顺序保留12路线完整资产", ("初步实验/可复用磨削测试集/test_ordered_holdout_assets.py",)),
    TestCommand("完整统计执行划分分母", ("初步实验/Geogram与PaMO组合验证/test_summary_split.py",)),
    TestCommand("CT物理面积实际回归", ("初步实验/可复用磨削测试集/test_ct_physical_repair_regression.py",)),
    TestCommand("薄壁编码退化实际回归", ("初步实验/可复用磨削测试集/test_thin_encoding_anchor_regression.py",)),
    TestCommand("冻结快照分块落盘", ("初步实验/Geogram与PaMO组合验证/test_frozen_snapshot_write.py",)),
    TestCommand("实验记录原子落盘", ("初步实验/Geogram与PaMO组合验证/test_atomic_record_write.py",)),
    TestCommand("初态编码退化锚点", ("初步实验/Geogram与PaMO组合验证/test_encoded_degenerate_anchors.py",)),
    TestCommand("初态编码锚点保存契约", ("初步实验/Geogram与PaMO组合验证/test_initial_encoding_saved_contract.py",)),
    TestCommand("完整路线边界恢复", ("初步实验/Geogram与PaMO组合验证/test_resume_completed_routes.py",)),
    TestCommand("初态规则同输入消融协议", ("初步实验/Geogram与PaMO组合验证/test_initial_encoding_ablation.py",)),
    TestCommand("新参数十二路线冻结资产", ("初步实验/可复用磨削测试集/test_initial_encoding_holdout.py",)),
    TestCommand("冻结评价清单核对", ("初步实验/Geogram与PaMO组合验证/test_frozen_local_evaluation.py",)),
    TestCommand(
        "来源约束v3冻结证据",
        ("初步实验/共同运动记录与方法对照/test_source_constrained_v3_freeze.py",),
    ),
    TestCommand("真实CT状态边界", ("初步实验/共同运动记录与方法对照/test_real_ct_state.py",)),
    TestCommand("持续状态时间线", ("初步实验/共同运动记录与方法对照/test_continuous_state_timeline.py",)),
    TestCommand("解析局部重建", ("初步实验/局部区域重建阶段一/test_patch.py",)),
    TestCommand("真实骨面投影", ("初步实验/真实骨面高度图验证/test_projection.py",)),
    TestCommand("真实骨面拼接", ("初步实验/真实骨面共边拼接/test_stitch.py",)),
    TestCommand("边界过渡带", ("初步实验/边界过渡带联合重建/test_joint.py",)),
    TestCommand("局部适用域", ("初步实验/局部适用域与核显计算/test_local.py",)),
    TestCommand("研究结果映射", ("初步实验/真实骨模型演示/test_research_results.py",)),
    TestCommand("轨迹覆盖", ("初步实验/CUDA真实骨面对照/test_coverage.py",)),
    TestCommand("增量缓存", ("初步实验/CUDA真实骨面对照/test_incremental.py",)),
    TestCommand(
        "默认在线算法",
        (
            "-m",
            "unittest",
            "test_validated_online.SessionTests.test_default_entry_and_explicit_legacy",
            "test_validated_online.SessionTests.test_full_sequence_matches_saved_experiment",
            "test_validated_online.SessionTests.test_rejection_does_not_publish",
            "test_validated_online.SessionTests.test_whole_audit_rejection_rolls_back",
        ),
        "初步实验/真实骨模型演示",
    ),
)

GUI_TESTS = (
    TestCommand(
        "Qt在线窗口",
        (
            "-m",
            "unittest",
            "test_validated_online.SessionTests.test_actual_gui_playback_and_camera",
        ),
        "初步实验/真实骨模型演示",
    ),
)

OPENCL_TESTS = (
    TestCommand("Intel OpenCL集成", ("初步实验/局部适用域与核显计算/test_integrated.py",)),
)

CUDA_TESTS = (
    TestCommand("CUDA查询", ("初步实验/CUDA真实骨面对照/test_cuda.py",)),
    TestCommand("CUDA区间", ("初步实验/CUDA真实骨面对照/test_interval.py",)),
    TestCommand("CUDA驻留缓存", ("初步实验/CUDA真实骨面对照/test_resident.py",)),
)


def _hardware_available(kind, root):
    if kind == "opencl":
        code = (
            "from integrated import SweepDevice; "
            "SweepDevice(); print('Intel FP64 OpenCL ready')"
        )
        cwd = root / "初步实验/局部适用域与核显计算"
    elif kind == "cuda":
        code = (
            "import cupy as cp; "
            "assert cp.cuda.runtime.getDeviceCount() == 1; print('CUDA ready')"
        )
        cwd = root
    else:
        return True
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        print(f"SKIP {kind}: {detail[-1] if detail else '硬件后端不可用'}")
        return False
    return True


def _run_commands(commands, root):
    failures = []
    for command in commands:
        print(f"\n==> {command.name}", flush=True)
        arguments = list(command.arguments)
        if arguments and not arguments[0].startswith("-"):
            arguments[0] = str(root / arguments[0])
        result = subprocess.run(
            [sys.executable, "-X", "utf8", *arguments],
            cwd=root / command.cwd,
        )
        if result.returncode:
            failures.append(command.name)
    return failures


def run_tests(suite="core"):
    """运行指定测试组并返回适合命令行退出的状态码。"""
    root = find_project_root()
    commands = []
    if suite in {"core", "all"}:
        commands.extend(CORE_TESTS)
    if suite in {"gui", "all"}:
        commands.extend(GUI_TESTS)
    if suite == "opencl" or (suite == "all" and _hardware_available("opencl", root)):
        commands.extend(OPENCL_TESTS)
    if suite == "cuda" or (suite == "all" and _hardware_available("cuda", root)):
        commands.extend(CUDA_TESTS)
    if suite in {"opencl", "cuda"} and not _hardware_available(suite, root):
        return 0

    failures = _run_commands(commands, root)
    print(f"\n完成：{len(commands) - len(failures)}/{len(commands)} 组通过")
    if failures:
        print("失败：" + "、".join(failures))
        return 1
    return 0
