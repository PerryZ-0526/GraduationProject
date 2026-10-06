"""复核连续输入的全分母、哈希、工具闭合性与对应运动端点。"""

import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from prepare_feedback import digest


def audit(root):
    manifest_path = root / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checked, rows = {}, []
    body_splits = {}
    for route in manifest["routes"]:
        passed = True
        body = route["initial_mesh_sha256"]
        previous = body_splits.setdefault(body, route["split"])
        passed = passed and previous == route["split"]
        expected = [(route["initial_mesh"], body), *[(t["mesh"], t["sha256"]) for t in route["prefix_tools"]]]
        for name, sha in expected:
            if name not in checked:
                path = root / "inputs" / name
                mesh = trimesh.load(path, force="mesh", process=False)
                checked[name] = {"sha256": digest(path), "closed": bool(mesh.is_watertight),
                                 "winding": bool(mesh.is_winding_consistent), "finite": bool(np.isfinite(mesh.vertices).all()),
                                 "nondegenerate": bool(np.all(mesh.area_faces > 1e-12))}
            item = checked[name]
            passed = passed and item["sha256"] == sha and all(item[key] for key in ("closed", "winding", "finite", "nondegenerate"))
        event_ids = [event["id"] for event in route["events"]]
        tool_ids = [tool["event_id"] for tool in route["prefix_tools"]]
        passed = passed and event_ids == route["cutting_prefix_ids"] == tool_ids and len(set(event_ids)) == len(event_ids)
        for event in route["events"]:
            points = np.array([event["explicit_sweep_start_mm"], event["position_mm"]])
            passed = passed and points.shape == (2, 3) and np.isfinite(points).all() and event["tool_radius_mm"] > 0
        rows.append({"id": route["id"], "passed": bool(passed), "prefixes": len(event_ids), "split": route["split"]})
    result = {"manifest_sha256": digest(manifest_path), "passed": all(r["passed"] for r in rows),
              "routes": len(rows), "prefixes": sum(r["prefixes"] for r in rows), "unique_files": len(checked),
              "rows": rows, "files": checked,
              "scope": "资产哈希、闭合性、绕序、退化与运动对应；未检查完整自交或执行CSG"}
    (root / "02-连续资产审计.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    result = audit(parser.parse_args().root)
    print(json.dumps({k: result[k] for k in ("passed", "routes", "prefixes", "unique_files")}), flush=True)
    raise SystemExit(0 if result["passed"] else 1)
