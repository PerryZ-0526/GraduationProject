"""从逐前缀审计结果打包合法Geogram输入，保留全部拒绝记录。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tarfile


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audits", type=Path, required=True)
    parser.add_argument("--geogram-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("输出目录已有文件，禁止覆盖")
    args.output.mkdir(parents=True, exist_ok=True)
    geogram = json.loads(args.geogram_record.read_text(encoding="utf-8"))
    expected = {(route["id"], prefix["event_id"]): prefix["sha256"]
                for route in geogram["routes"] for prefix in route["prefixes"]
                if prefix["status"] in {"computed", "contained_reused"}}
    if len(geogram["routes"]) != 6 or len(expected) != 24:
        raise ValueError("Geogram开发前缀数量不符")
    now = datetime.now(timezone(timedelta(hours=8)))
    manifest = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
                "geogram_record_sha256": sha256(args.geogram_record),
                "cleanup": "Trimesh process=True, validate=True; output reloaded and audited",
                "valid": [], "rejected": []}
    observed = set()
    archive_path = args.output / "开发合法前缀包.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for report in sorted(args.audits.glob("*/01-逐前缀输入审计.json")):
            route = report.parent.name
            audit = json.loads(report.read_text(encoding="utf-8"))
            for row in audit["rows"]:
                key = route, row["event"]
                if key in observed or expected.get(key) != row["raw_sha256"]:
                    raise ValueError(f"{key}: 原始网格与远端记录不符或重复")
                observed.add(key)
                data = {"route": route, "event": row["event"],
                        "raw_sha256": row["raw_sha256"],
                        "audit_sha256": sha256(report),
                        "max_raw_vertex_to_clean_vertex_mm": row["max_raw_vertex_to_clean_vertex_mm"],
                        "volume_delta_mm3": row["volume_delta_mm3"]}
                if row["valid_pamo_input_under_listed_checks"]:
                    path = Path(row["clean_path"])
                    if sha256(path) != row["clean_sha256"]:
                        raise ValueError(f"{key}: 清理副本哈希不符")
                    name = f"valid_inputs/{route}/{row['event']}.obj"
                    archive.add(path, arcname=name)
                    manifest["valid"].append({**data, "path": name,
                                              "sha256": row["clean_sha256"]})
                else:
                    manifest["rejected"].append({**data, "raw": row["raw"],
                                                 "clean": row["clean"]})
        if observed != set(expected) or len(manifest["valid"]) != 21 or len(manifest["rejected"]) != 3:
            raise ValueError("逐前缀审计覆盖不完整")
        manifest_path = args.output / "01-开发合法前缀清单.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        archive.add(manifest_path, arcname=manifest_path.name)
    print(json.dumps({"valid": len(manifest["valid"]), "rejected": len(manifest["rejected"]),
                      "archive_sha256": sha256(archive_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
