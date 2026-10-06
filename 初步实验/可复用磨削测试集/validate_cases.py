"""核对冻结测试资产摘要、拓扑和路线，保存可复用资产审计。"""

import hashlib
import json
from pathlib import Path
import numpy as np
import trimesh


def audit(root):
    manifest = json.loads((root / "01-测试集清单.json").read_text(encoding="utf-8"))
    rows = []
    for body in manifest["bodies"]:
        path = root / body["mesh"]
        mesh = trimesh.load(path, force="mesh", process=False)
        valid = (hashlib.sha256(path.read_bytes()).hexdigest() == body["sha256"] and mesh.is_watertight
                 and mesh.is_winding_consistent and np.isfinite(mesh.vertices).all() and np.all(mesh.area_faces > 1e-12))
        for route in body["routes"]:
            path = root / route["file"]
            motion = json.loads(path.read_text(encoding="utf-8"))
            valid = valid and hashlib.sha256(path.read_bytes()).hexdigest() == route["sha256"]
            valid = valid and motion["body_id"] == body["id"] and motion["tool_radius_mm"] > 0
            positions = np.array([e["position_mm"] for e in motion["events"]])
            valid = valid and positions.shape == (route["segments"] + 1, 3) and np.isfinite(positions).all()
        rows.append({"id": body["id"], "passed": bool(valid), "split": body["split"]})
    result = {"passed": all(row["passed"] for row in rows), "bodies": len(rows),
              "routes": sum(len(b["routes"]) for b in manifest["bodies"]), "rows": rows,
              "scope": "资产哈希、闭合性、绕序、面积和运动格式；没有运行布尔或质量维护"}
    (root / "02-测试资产审计.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = audit(Path(__file__).resolve().parent / "合成输入_v1")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)
