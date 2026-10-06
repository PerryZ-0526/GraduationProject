"""对被FP32输入门控拒绝的网格执行隔离诊断，不发布或回灌状态。"""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from run_surface_band_feedback import SurfaceBandEngine
import run_adaptive_feedback as adaptive
from exact_alarm_contact import mesh_valid_exact_contacts
from audit_followup_candidate import sha256
from run_geometry_study import now, save, retrieve


def main(engine_type=SurfaceBandEngine):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "tool", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    mesh = trimesh.load(args.source, process=False)
    # 同作者process的均值平移和最大轴归一化，诊断真实FP32坐标中的零面积。
    scale = 1.0 / np.ptp(mesh.vertices, axis=0).max()
    normalized = (mesh.vertices * scale - mesh.vertices.mean(axis=0) * scale).astype(np.float32).astype(float)
    tri = normalized[mesh.faces]
    areas = np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1)*.5
    _, metrics = mesh_valid_exact_contacts(mesh)
    record = dict(time_beijing=now(), status="running", published=False, rows=[], input_metrics=metrics,
        author_normalized_fp32_exact_zero_faces=int(np.count_nonzero(areas == 0)),
        input_sha256={name: sha256(getattr(args, name)) for name in ("source", "labels", "tool")},
        scope="绕过正式输入门控的隔离数值诊断；不发布、不续跑、不改变原验收和失败记录")
    for name in ("source", "labels", "tool"):
        (args.output / (name + getattr(args, name).suffix)).write_bytes(getattr(args, name).read_bytes())
    (args.output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    # 隔离诊断可注入独立冻结的引擎，默认仍沿用原表面邻域版本。
    engine = engine_type(args.output, args.port)
    try:
        record["setup"] = engine.setup()
        adaptive.mesh_valid = mesh_valid_exact_contacts
        save(args.output / "01-输入门控外GPU数值诊断.json", record)
        for method in ("boolean", "expanded"):
            folder = args.output / method
            row = engine.run(args.source, args.labels, args.tool, method, folder)
            row = adaptive.audit_adaptive(args.source, args.tool, args.labels, folder, row)
            # 每种方法立即归档求导轨迹，避免下一独立进程覆盖共享模块的诊断文件。
            trace = engine.remote + "/diff_trace.json"
            try:
                retrieve(engine.client, engine.sftp, trace, folder / "diff_trace.json")
                engine.sftp.rename(trace, engine.remote + "/" + method + "_diff_trace.json")
                row["diff_trace_sha256"] = sha256(folder / "diff_trace.json")
                # 几何审计字段保留原义；内部总能量非有限必须另记为数值失败。
                calls = json.loads((folder / "diff_trace.json").read_text(encoding="utf-8"))["rows"]
                row["numerical_diagnostic"] = dict(diff_calls=len(calls),
                    finite_energy_calls=sum(item["full_energy_finite"] for item in calls),
                    finite_free_derivative_calls=sum(not item["nonfinite_free_vertices"] for item in calls),
                    passed=bool(calls and all(item["full_energy_finite"] and item["finite_positions"]
                                and not item["nonfinite_free_vertices"] for item in calls)))
            except FileNotFoundError:
                row["diff_trace_available"] = False
            record["rows"].append(row)
            save(args.output / "01-输入门控外GPU数值诊断.json", record)
            print(method, row["status"], flush=True)
        record.update(status="completed_with_recorded_outcomes", finished_beijing=now())
        save(args.output / "01-输入门控外GPU数值诊断.json", record)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
