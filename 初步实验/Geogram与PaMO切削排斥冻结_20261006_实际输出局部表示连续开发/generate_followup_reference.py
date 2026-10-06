"""由冻结解析材料场生成单个切削前缀的三维离散参照网格。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pyvista as pv

from followup_reference import audit, material_field


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference_mesh(route: dict, event_id: str, spacing: float) -> tuple[pv.PolyData, dict]:
    """在完整实体周围留两格空白，并以三维等值面保存回折与侧壁。"""
    body = route["analytic_body"]
    margin = 2 * spacing
    if body["kind"] == "sphere":
        bounds = [(-2.5 - margin, 2.5 + margin)] * 3
    else:
        xmin, xmax, ymin, ymax = body["bounds_xy_mm"]
        a, b = body["slope_xy"]
        top = max(a * x + b * y for x in (xmin, xmax) for y in (ymin, ymax))
        bounds = [(xmin - margin, xmax + margin), (ymin - margin, ymax + margin),
                  (body["bottom_z_mm"] - margin, top + margin)]
    axes = [np.arange(low, high + spacing / 2, spacing, dtype=np.float64)
            for low, high in bounds]
    x, y, z = axes
    xx, yy = np.meshgrid(x, y, indexing="ij")
    xy = np.column_stack((xx.ravel(order="F"), yy.ravel(order="F")))
    values = np.empty((len(x), len(y), len(z)), dtype=np.float32)
    for index, z_value in enumerate(z):
        points = np.column_stack((xy, np.full(len(xy), z_value)))
        values[:, :, index] = material_field(points, route, event_id).reshape(
            len(x), len(y), order="F")
    grid = pv.ImageData(dimensions=values.shape, spacing=(spacing, spacing, spacing),
                        origin=(float(x[0]), float(y[0]), float(z[0])))
    grid.point_data["analytic_material_field"] = values.ravel(order="F")
    surface = grid.contour([0.0], scalars="analytic_material_field").triangulate()
    if surface.n_cells == 0:
        raise RuntimeError(f"{route['id']}/{event_id}: 参照等值面为空")
    # 场残差只检查生成器数值一致性，不代表双向表面距离上界。
    probes = np.asarray(surface.points, dtype=np.float64)
    max_residual = max(float(np.max(np.abs(material_field(probes[start:start + 20000],
                                                       route, event_id))))
                       for start in range(0, len(probes), 20000))
    return surface, {"grid_dimensions": list(values.shape), "vertices": surface.n_points,
                     "faces": surface.n_cells, "max_analytic_field_residual_mm": max_residual}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--spacing-mm", type=float, default=0.025)
    args = parser.parse_args()
    if args.spacing_mm <= 0:
        raise ValueError("参照网格间距必须为正")
    frozen = args.frozen.resolve()
    audit(frozen)
    manifest_path = frozen / "01-冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matches = [item for item in manifest["routes"] if item["id"] == args.route]
    if len(matches) != 1:
        raise ValueError("路线ID未登记或不唯一")
    route = matches[0]
    if args.event not in route["cutting_prefix_ids"]:
        raise ValueError("事件不是登记的切削前缀")
    output = args.output.resolve()
    if output.exists() or output.with_suffix(".json").exists():
        raise ValueError("参照输出已存在，禁止覆盖")
    output.parent.mkdir(parents=True, exist_ok=True)
    surface, diagnostics = reference_mesh(route, args.event, args.spacing_mm)
    surface.save(output)
    now = datetime.now(timezone(timedelta(hours=8)))
    record = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "route": route["id"], "event": args.event,
              "frozen_manifest_sha256": sha256(manifest_path),
              "reference_code_sha256": sha256(Path(__file__)),
              "spacing_mm": args.spacing_mm, "reference_file": output.name,
              "reference_sha256": sha256(output),
              "interpretation": "解析场规则等值面；离散误差未界定，不是连续Hausdorff证书",
              **diagnostics}
    output.with_suffix(".json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **diagnostics}, ensure_ascii=False))


if __name__ == "__main__":
    main()
