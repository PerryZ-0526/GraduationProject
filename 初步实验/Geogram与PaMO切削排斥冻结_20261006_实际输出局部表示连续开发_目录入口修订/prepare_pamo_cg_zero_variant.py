"""制作去除共轭梯度循环重复清零的 PaMO 隔离副本。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


EXPECTED_CG_SHA256 = "e37f579478c0618fa0f3919d2919d6584d62376e909a902ae295acc1af1db7fc"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_package.resolve()
    destination = args.destination.resolve()
    target = destination / "pamo_safe_project"
    if target.exists():
        raise FileExistsError(target)
    cg_source = source / "cg_solver.py"
    if sha256(cg_source) != EXPECTED_CG_SHA256:
        raise ValueError("作者CG源码哈希变化，停止制作变体")
    system_source = (source / "system.py").read_text(encoding="utf-8")
    if system_source.count("    def _compute_hess_dx(self, dx: wp.array, hess_dx: wp.array):\n        hess_dx.zero_()\n") != 1:
        raise ValueError("Hessian向量积入口不再保证清零，停止制作变体")
    shutil.copytree(source, target)
    cg_target = target / "cg_solver.py"
    content = cg_target.read_text(encoding="utf-8")
    old = "        for cg_iter in range(c.n_cg_iters):\n            self.A_v.zero_()\n            s._compute_hess_dx(self.v, self.A_v)\n"
    new = ("        for cg_iter in range(c.n_cg_iters):\n"
           "            # Hessian向量积入口已清零A_v，此处不重复清零。\n"
           "            s._compute_hess_dx(self.v, self.A_v)\n")
    if content.count(old) != 1:
        raise ValueError("作者CG循环锚点变化")
    cg_target.write_text(content.replace(old, new), encoding="utf-8")
    record = {"source_cg_sha256": EXPECTED_CG_SHA256,
              "variant_cg_sha256": sha256(cg_target),
              "source_system_sha256": sha256(source / "system.py"),
              "change": "删除每次CG迭代内与Hessian向量积入口重复的A_v清零"}
    (destination / "variant.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
