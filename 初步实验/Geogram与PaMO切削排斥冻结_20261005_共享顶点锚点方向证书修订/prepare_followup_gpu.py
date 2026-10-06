"""只打包冻结开发路线与符号反例，避免独立测试输入进入调参批次。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tarfile

from followup_reference import audit


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frozen = args.frozen.resolve()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("开发包目录已含文件，禁止覆盖")
    checked = audit(frozen)
    if checked["development"] != 6 or checked["evaluation"] != 12:
        raise ValueError("冻结路线数量不符")
    source = json.loads((frozen / "01-冻结清单.json").read_text(encoding="utf-8"))
    development = [route for route in source["routes"] if route["split"] == "development"]
    output.mkdir(parents=True, exist_ok=True)
    selected = {"schema_version": 1, "routes": development,
                "negative_inputs": source["negative_inputs"],
                "frozen_manifest_sha256": sha256(frozen / "01-冻结清单.json")}
    selected_path = output / "01-开发输入清单.json"
    selected_path.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = {frozen / "02-评价协议.json": "02-评价协议.json",
             selected_path: selected_path.name}
    for route in development:
        files[frozen / route["initial_mesh"]] = route["initial_mesh"]
        for tool in route["prefix_tools"]:
            files[frozen / tool["mesh"]] = tool["mesh"]
    for negative in source["negative_inputs"]:
        files[frozen / negative["mesh"]] = negative["mesh"]
    archive = output / "开发输入包.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for source_path, name in sorted(files.items(), key=lambda item: item[1]):
            bundle.add(source_path, arcname=name)
    now = datetime.now(timezone(timedelta(hours=8)))
    package = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
               "frozen_manifest_sha256": selected["frozen_manifest_sha256"],
               "archive": archive.name, "archive_sha256": sha256(archive),
               "development_routes": len(development), "evaluation_routes_in_package": 0,
               "negative_inputs": len(source["negative_inputs"]),
               "files": [{"name": name, "sha256": sha256(path)} for path, name in
                         sorted(files.items(), key=lambda item: item[1])]}
    (output / "02-打包记录.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "sha256": package["archive_sha256"],
                      "development": len(development), "negative": len(source["negative_inputs"])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
