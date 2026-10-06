"""由解析材料场生成独立三维离散参照，保留回折和侧壁。"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pyvista as pv


ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "初步实验/共同运动记录与方法对照"
sys.path.insert(0, str(COMMON))

from motion_record import initial_field, load_document, motion_field, replay_case


SPACING_MM = 0.025
XY_LIMIT_MM = 2.0
BOTTOM_MM = -0.9


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def field_slice(xy, z, case, replay):
    points = np.column_stack((xy, np.full(len(xy), z)))
    material = np.maximum(initial_field(points, case), -motion_field(points, replay))
    bounds = np.maximum.reduce((
        -points[:, 0] - XY_LIMIT_MM,
        points[:, 0] - XY_LIMIT_MM,
        -points[:, 1] - XY_LIMIT_MM,
        points[:, 1] - XY_LIMIT_MM,
        BOTTOM_MM - points[:, 2],
    ))
    return np.maximum(material, bounds)


def generate(case, policy, target):
    replay = replay_case(case, policy)
    a, b, offset = case["initial_surface"]["height_coefficients"]
    top = offset + XY_LIMIT_MM * (abs(a) + abs(b))
    margin = 2 * SPACING_MM
    x = np.arange(-XY_LIMIT_MM - margin, XY_LIMIT_MM + margin + SPACING_MM / 2, SPACING_MM)
    y = x.copy()
    z = np.arange(BOTTOM_MM - margin, top + margin + SPACING_MM / 2, SPACING_MM)
    # 网格采用Fortran顺序，与VTK ImageData的点编号保持一致。
    xx, yy = np.meshgrid(x, y, indexing="ij")
    xy = np.column_stack((xx.ravel(order="F"), yy.ravel(order="F")))
    values = np.empty((len(x), len(y), len(z)), dtype=np.float32)
    for index, z_value in enumerate(z):
        values[:, :, index] = field_slice(xy, z_value, case, replay).reshape(
            len(x), len(y), order="F"
        )
    grid = pv.ImageData(
        dimensions=values.shape,
        spacing=(SPACING_MM, SPACING_MM, SPACING_MM),
        origin=(float(x[0]), float(y[0]), float(z[0])),
    )
    grid.point_data["material_field"] = values.ravel(order="F")
    surface = grid.contour([0.0], scalars="material_field").triangulate()
    if surface.n_cells == 0:
        raise RuntimeError(f"三维参照为空: {case['id']}")
    surface.save(target)
    return {"vertices": surface.n_points, "faces": surface.n_cells, "grid_dimensions": list(values.shape)}


def main():
    now = datetime.now(timezone(timedelta(hours=8)))
    output = Path(__file__).resolve().parent / "实验结果" / (now.strftime("%Y%m%d_%H%M%S") + "_analytic_reference")
    output.mkdir(parents=True, exist_ok=False)
    documents = [COMMON / "quality_failure_cases_v2.json", COMMON / "cases.json"]
    rows = []
    for path in documents:
        document = load_document(path)
        for case in document["cases"]:
            if case["id"] not in {
                "challenge_v2_raw_failure_a011", "challenge_v2_raw_failure_a015",
                "challenge_v2_raw_failure_a019", "challenge_v2_raw_failure_a023",
                "tilted_crossing_paths",
            }:
                continue
            target = output / f"{case['id']}.vtp"
            diagnostics = generate(case, document["replay_policy"], target)
            rows.append({
                "case_id": case["id"], "case_document": str(path),
                "case_document_sha256": file_hash(path), "reference": str(target),
                "sha256": file_hash(target), **diagnostics,
            })
            print(case["id"], diagnostics["faces"], flush=True)
    manifest = {
        "schema_version": 1,
        "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
        "spacing_mm": SPACING_MM,
        "xy_bounds_mm": [-XY_LIMIT_MM, XY_LIMIT_MM, -XY_LIMIT_MM, XY_LIMIT_MM],
        "bottom_mm": BOTTOM_MM,
        "interpretation": "解析三维材料场的规则网格等值面；是离散参照，不是连续Hausdorff证书",
        "references": rows,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
