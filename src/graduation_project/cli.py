"""毕业课题仓库的统一命令行接口。"""
from importlib import metadata
import argparse
import os
import platform
import sys

from .project import find_project_root
from .test_runner import run_tests


CORE_PACKAGES = (
    "numpy",
    "scipy",
    "trimesh",
    "manifold3d",
    "pymeshlab",
    "triangle",
    "vtk",
    "pyvista",
    "pyvistaqt",
    "PyQt6",
)


def show_info():
    root = find_project_root()
    print(f"项目根目录: {root}")
    print(f"Python: {platform.python_version()} ({platform.machine()}, {sys.platform})")
    print(f"解释器: {sys.executable}")
    print("核心依赖:")
    for package in CORE_PACKAGES:
        try:
            version = metadata.version(package)
        except metadata.PackageNotFoundError:
            version = "未安装"
        print(f"  {package}: {version}")


def launch_gui(arguments):
    root = find_project_root()
    script = root / "初步实验/真实骨模型演示/real_bone_interactive_app.py"
    os.execv(sys.executable, [sys.executable, str(script), *arguments])


def build_parser():
    parser = argparse.ArgumentParser(
        prog="graduation-project",
        description="骨表面增量重建与实时可视化研究工具",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("info", help="显示当前项目与运行环境")
    tests = subparsers.add_parser("test", help="运行统一回归测试")
    tests.add_argument(
        "--suite",
        choices=("core", "gui", "opencl", "cuda", "all"),
        default="core",
        help="测试组；默认core，all会自动跳过不可用硬件",
    )
    subparsers.add_parser("gui", help="启动默认在线窗口，其余参数透传给原入口")
    return parser


def main():
    parser = build_parser()
    args, extra = parser.parse_known_args()
    if args.command == "info":
        if extra:
            parser.error("info命令不接受额外参数")
        show_info()
        return 0
    if args.command == "test":
        if extra:
            parser.error("test命令不接受额外参数")
        return run_tests(args.suite)
    if args.command == "gui":
        launch_gui(extra)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
