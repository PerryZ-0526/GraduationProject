"""项目根目录发现及研究脚本启动工具。"""
from pathlib import Path
import os


MARKERS = ("研究内容.md", "初步实验")


def _is_project_root(path):
    return all((path / marker).exists() for marker in MARKERS)


def find_project_root(start=None):
    """查找包含研究范本和实验目录的仓库根目录。"""
    candidates = []
    configured = os.environ.get("GRADUATION_PROJECT_ROOT")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend((Path(start or Path.cwd()), Path(__file__).resolve().parents[2]))

    visited = set()
    for candidate in candidates:
        for path in (candidate.resolve(), *candidate.resolve().parents):
            if path in visited:
                continue
            visited.add(path)
            if _is_project_root(path):
                return path
    raise RuntimeError(
        "未找到项目根目录；请在仓库内运行，或设置GRADUATION_PROJECT_ROOT。"
    )
