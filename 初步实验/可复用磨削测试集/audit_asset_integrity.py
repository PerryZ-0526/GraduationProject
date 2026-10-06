"""只读核对连续输入和冻结文件包，保留未支持格式及失配负例。"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_package(package, manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    references = []
    if manifest_path.name == "01-完整范围冻结清单.json":
        for route in manifest["routes"]:
            references.append(("inputs/"+route["initial_mesh"], route["initial_mesh_sha256"]))
            references.extend(("inputs/"+t["mesh"], t["sha256"]) for t in route["prefix_tools"])
    elif "files" in manifest and all("file" in f and "sha256" in f for f in manifest["files"]):
        references = [(f["file"], f["sha256"]) for f in manifest["files"]]
    else:
        return dict(package=str(package), manifest_sha256=digest(manifest_path),
            status="unsupported_manifest_schema", scope="没有猜测文件字段或改写清单")
    rows = []
    expected = {}
    for name, sha in references:
        target = (package/name).resolve()
        # 清单只能引用本包内文件，不能通过相对路径借用其他资产的摘要。
        if not target.is_relative_to(package.resolve()):
            raise ValueError("清单引用超出资产包："+name)
        if name in expected:
            if expected[name] != sha:
                raise ValueError("同一文件存在冲突摘要："+name)
            continue
        expected[name] = sha
        actual = digest(target) if target.is_file() else None
        rows.append(dict(file=name, expected_sha256=sha, actual_sha256=actual, passed=actual == sha))
    return dict(package=str(package), manifest_sha256=digest(manifest_path),
        status="checked", files=len(rows), hashes_match=all(r["passed"] for r in rows), rows=rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    omitted = []
    for package in sorted(p for p in args.root.iterdir() if p.is_dir() and p.name != "__pycache__"):
        manifests = [package/name for name in ("01-完整范围冻结清单.json", "01-冻结清单.json") if (package/name).exists()]
        if not manifests:
            omitted.append(dict(package=str(package), reason="不是本入口支持的两类冻结清单"))
        for manifest in manifests:
            rows.append(check_package(package, manifest))
    checked = [r for r in rows if r["status"] == "checked"]
    result = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        scope="当前发现的连续输入及files冻结包摘要；未支持包单列，不证明几何、独立性或算法通过",
        auditor_sha256=digest(Path(__file__)), checked_manifests=len(checked),
        referenced_files=sum(r["files"] for r in checked),
        all_checked_hashes_match=all(r["hashes_match"] for r in checked), rows=rows, omitted=omitted)
    # 复核结果使用独立路径，历史审计和原冻结清单不覆盖。
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print("checked", len(checked), "files", result["referenced_files"], "hashes", result["all_checked_hashes_match"])
    if not result["all_checked_hashes_match"]:
        raise SystemExit(1)
