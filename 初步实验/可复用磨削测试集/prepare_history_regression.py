"""登记历史开发路线供输入门控消融复用，保留旧哈希与已见身份。"""

import json
from pathlib import Path
import shutil
from prepare_feedback import HERE, digest


def main():
    frozen = HERE.parent / "Geogram与PaMO组合验证/实验结果/20260928_后续输入冻结_v3"
    path = frozen / "01-冻结清单.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    routes = [r for r in original["routes"] if r["split"] == "development"]
    output = HERE / "历史开发反馈回归_v1"
    inputs = output / "inputs"
    inputs.mkdir(parents=True, exist_ok=False)
    for route in routes:
        items = [(route["initial_mesh"], route["initial_mesh_sha256"]), *[(t["mesh"], t["sha256"]) for t in route["prefix_tools"]]]
        for name, expected in items:
            source = frozen / name
            if digest(source) != expected:
                raise ValueError("历史开发输入摘要改变")
            shutil.copyfile(source, inputs / name)
    manifest = {"parent_manifest_sha256": digest(path), "generator_sha256": digest(Path(__file__)),
                "routes": routes, "negative_inputs": [], "scope": "六条已见历史开发路线，不是新独立输入",
                "replay_policy": {"late_event": "reject", "max_link_gap_ms": 200}}
    (output / "01-完整范围冻结清单.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("routes", len(routes), "prefixes", sum(len(r["cutting_prefix_ids"]) for r in routes), flush=True)


if __name__ == "__main__":
    main()
