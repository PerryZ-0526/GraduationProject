"""隔离macOS上的PyMeshLab Qt5运行时，避免与PyQt6同进程冲突。"""
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np


def _compute_flags(vertices, faces):
    """在当前进程执行PyMeshLab自相交检测。"""
    import pymeshlab

    meshset = pymeshlab.MeshSet()
    meshset.add_mesh(pymeshlab.Mesh(vertices, faces))
    meshset.compute_selection_by_self_intersections_per_face()
    return np.asarray(meshset.current_mesh().face_selection_array(), dtype=bool)


def self_intersection_flags(vertices, faces):
    """返回逐面自相交标记；macOS使用子进程隔离PyMeshLab自带的Qt5。"""
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    if sys.platform != "darwin":
        return _compute_flags(vertices, faces)

    with tempfile.TemporaryDirectory(prefix="pymeshlab-audit-") as folder:
        folder = Path(folder)
        input_path = folder / "mesh.npz"
        output_path = folder / "flags.npy"
        np.savez(input_path, vertices=vertices, faces=faces)
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), str(input_path), str(output_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        flags = np.load(output_path, allow_pickle=False)
    if flags.shape != (len(faces),):
        raise RuntimeError("PyMeshLab子进程返回的自相交标记尺寸不正确")
    return flags


def main():
    """子进程入口，只加载PyMeshLab，不加载任何Qt界面绑定。"""
    if len(sys.argv) != 3:
        raise SystemExit("usage: pymeshlab_isolation.py INPUT_NPZ OUTPUT_NPY")
    data = np.load(sys.argv[1], allow_pickle=False)
    np.save(sys.argv[2], _compute_flags(data["vertices"], data["faces"]))


if __name__ == "__main__":
    main()
