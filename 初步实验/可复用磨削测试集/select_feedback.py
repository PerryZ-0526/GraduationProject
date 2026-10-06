"""按预声明划分和路线类别选择执行批次，保持全部输入摘要与父清单身份。"""

import argparse
import json
from pathlib import Path
import shutil
from prepare_feedback import digest


def select(source, output, split, category):
    path = source / "01-完整范围冻结清单.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    routes = [r for r in manifest["routes"] if r["split"] == split and r["category"] == category]
    if not routes:
        raise ValueError("选择条件没有路线")
    inputs = output / "inputs"
    inputs.mkdir(parents=True, exist_ok=False)
    copied = set()
    for route in routes:
        items = [(route["initial_mesh"], route["initial_mesh_sha256"]), *[(t["mesh"], t["sha256"]) for t in route["prefix_tools"]]]
        for name, expected in items:
            original = source / "inputs" / name
            if digest(original) != expected:
                raise ValueError("冻结输入摘要改变")
            if name not in copied:
                shutil.copyfile(original, inputs / name)
                copied.add(name)
    manifest.update(routes=routes, parent_manifest_sha256=digest(path), selection={"split": split, "category": category})
    (output / path.name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("routes", len(routes), "prefixes", sum(len(r["cutting_prefix_ids"]) for r in routes), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--split", required=True)
    parser.add_argument("--category", required=True)
    args = parser.parse_args()
    select(args.source, args.output, args.split, args.category)
