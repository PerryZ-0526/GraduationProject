"""在候选运行前登记各解析切削前缀的预期拓扑与重复事件。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    args = parser.parse_args()
    root = args.frozen.resolve()
    target = root / "03-逐前缀拓扑预期.json"
    if target.exists():
        raise ValueError("预期附表已冻结，禁止覆盖")
    manifest_path = root / "01-冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    for route in manifest["routes"]:
        prefixes = []
        for event_id in route["cutting_prefix_ids"]:
            prefixes.append({
                "event_id": event_id,
                "expected_components": 1,
                "expected_cavities": 0,
                "expected_genus": 0,
                "expected_watertight": True,
                "expected_no_geometry_change_from_prior_cut":
                    route["category"] == "repeat" and event_id == "e2",
            })
        rows.append({"id": route["id"], "prefixes": prefixes})
    now = datetime.now(timezone(timedelta(hours=8)))
    addendum = {
        "schema_version": 1,
        "生成时间": now.strftime("%Y年%m月%d日%H时%M分%S秒（北京时间）"),
        "修改时间及修改内容": "首次生成：在新候选运行前登记解析路线逐前缀拓扑预期。",
        "文档概述": "该附表由原冻结路线的浅表面切削几何预先推断，不读取PaMO或Q输出。",
        "索引目录": ["原清单哈希", "预期依据", "逐路线前缀"],
        "frozen_manifest_sha256": sha256(manifest_path),
        "reason": "工具半径0.7 mm、切入深度至多约0.325 mm；板体底部与球体深部保留连续材料，球形扫掠均从外部接触表面，无预设封闭内腔或切断主体。边缘路线允许穿过板体侧面。",
        "status": "analytic_expectation_pending_independent_geometry_check",
        "routes": rows,
    }
    target.write_text(json.dumps(addendum, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"file": str(target), "sha256": sha256(target),
                      "routes": len(rows), "prefixes": sum(len(row["prefixes"]) for row in rows)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
