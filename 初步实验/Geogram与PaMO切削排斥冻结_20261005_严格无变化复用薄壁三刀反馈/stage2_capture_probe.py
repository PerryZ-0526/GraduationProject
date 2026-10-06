"""在既有符号诊断运行中只记录阶段二到阶段三的交接网格。"""

import sys
from pathlib import Path

import pamo_safe_project
import trimesh

import sign_constraint_probe


def main():
    output_dir = Path(sys.argv[sys.argv.index("--output-dir") + 1])
    original_process = pamo_safe_project.process

    def capture_process(source_vertices, source_faces, vertices, faces, *args, **kwargs):
        # 阶段二输出由作者原调用直接传入，记录后继续原阶段三。
        trimesh.Trimesh(vertices=vertices, faces=faces, process=False).export(
            output_dir / "stage2.obj"
        )
        return original_process(source_vertices, source_faces, vertices, faces,
                                *args, **kwargs)

    pamo_safe_project.process = capture_process
    try:
        sign_constraint_probe.main()
    finally:
        pamo_safe_project.process = original_process


if __name__ == "__main__":
    main()
