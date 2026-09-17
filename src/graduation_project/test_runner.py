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
    TestCommand("竖直磨削分层", ("初步实验/竖直磨削曲面分层/test_axis.py",)),
    TestCommand("计划裁剪特征重建", ("初步实验/计划裁剪特征重建/test_clipped_patch.py",)),
    TestCommand("共同运动记录", ("初步实验/共同运动记录与方法对照/test_motion_record.py",)),
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
