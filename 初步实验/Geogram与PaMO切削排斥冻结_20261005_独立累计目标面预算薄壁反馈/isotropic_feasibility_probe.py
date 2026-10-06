"""用固定等长重网格配置探查局部质量操作是否值得继续研究。"""

import argparse
from pathlib import Path
import tempfile

import pymeshlab


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    mesh_set = pymeshlab.MeshSet()
    mesh_set.load_new_mesh(str(args.input))
    # 固定几何距离限制；具体是否守住原曲面仍由独立审计判定。
    mesh_set.apply_filter(
        "meshing_isotropic_explicit_remeshing",
        iterations=10,
        targetlen=pymeshlab.PureValue(0.06),
        featuredeg=30.0,
        checksurfdist=True,
        maxsurfdist=pymeshlab.PureValue(0.02),
    )
    # Windows 下 PyMeshLab 导出中文路径会解码失败，先写入英文临时路径。
    with tempfile.TemporaryDirectory(prefix="pamo_iso_") as temporary:
        exported = Path(temporary) / "output.obj"
        mesh_set.save_current_mesh(str(exported))
        args.output.write_bytes(exported.read_bytes())


if __name__ == "__main__":
    main()
