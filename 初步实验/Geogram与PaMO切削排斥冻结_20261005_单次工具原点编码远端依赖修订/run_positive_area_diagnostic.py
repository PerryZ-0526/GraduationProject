"""极小正面积输入的原版PaMO诊断；不改变正式发布协议，不回灌状态。"""

import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from run_constrained_batch import RemoteQuality, HERE
from run_adaptive_feedback import audit_adaptive
from audit_followup_candidate import sha256
from run_geometry_study import save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"time_beijing": now(), "status": "running", "rows": [],
              "scope": "五张已见输入；输入近面积门槛的诊断例外，没有发布或连续反馈，原始记录不改写"}
    batch = HERE / "实验结果/20261004_局部维护六路线C1开发_清理与复用"
    old = json.loads((batch / "01-局部C1逐帧执行与独立审计.json").read_text(encoding="utf-8"))
    frozen = HERE / "实验结果/20260928_后续输入冻结_v3"
    manifest = json.loads((frozen / "01-冻结清单.json").read_text(encoding="utf-8"))
    engine = RemoteQuality(args.output, args.port)
    try:
        report["environment"] = engine.setup()
        for old_row in old["rows"]:
            if old_row["status"] != "retained_parent_and_stopped":
                continue
            case = old_row["route"] + "_" + old_row["event"]
            folder = batch / case
            source = folder / "source_clean.obj"
            labels = folder / "labels_clean.json"
            mesh = trimesh.load(source, force="mesh", process=False)
            area_metrics = []
            for coordinates in (mesh.vertices.astype(np.float64), mesh.vertices.astype(np.float32)):
                triangles = coordinates[mesh.faces]
                area = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1) / 2
                area_metrics.append({"dtype": str(coordinates.dtype), "true_zero_faces": int((area == 0).sum()),
                                     "small_positive_faces": int(((area > 0) & (area <= 1e-12)).sum()), "minimum_area_mm2": float(area.min())})
            route = next(r for r in manifest["routes"] if r["id"] == old_row["route"])
            tool = frozen / next(t["mesh"] for t in route["prefix_tools"] if t["event_id"] == old_row["event"])
            target = args.output / case
            if not np.isfinite(mesh.vertices).all() or any(item["true_zero_faces"] for item in area_metrics):
                row = {"status": "actual_zero_or_nonfinite_input_rejected"}
            else:
                row = engine.run(source, labels, tool, "full", target)
                row = audit_adaptive(source, tool, labels, target, row)
            row.update(case=case, input_sha256=sha256(source), area_arithmetic=area_metrics, published=False)
            report["rows"].append(row)
            save(args.output / "01-极小正面积GPU诊断.json", report)
            print(case, row["status"], flush=True)
        report["status"] = "completed_with_recorded_failures"
        save(args.output / "01-极小正面积GPU诊断.json", report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
