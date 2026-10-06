"""按冻结计划汇总全范围质量、误差与失败，未执行内容明确保留。"""

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics

from audit_followup_candidate import sha256
from run_geometry_study import save, now


def median(values):
    """缺失指标保留空值，不能将未执行帧作为零误差或零耗时。"""
    return statistics.median(values) if values else None


def distributions(rows):
    """仅对实际发布网格汇总，全网格和物理扫掠邻域使用各自面分母。"""
    published = [r for r in rows if r["status"] == "published_under_sampled_and_vertex_protocol"]
    result = {"planned_records_present": len(rows), "status_counts": dict(Counter(r["status"] for r in rows)),
        "published_frames": len(published), "selected_methods": dict(Counter(r["selected_method"] for r in published)),
        "published_zero_nominal_removal_frames": sum(abs(r["signed_removed_volume_mm3"]) <= 1e-8 for r in published),
        "median_frame_wall_including_audit_ms": median([r["frame_wall_including_audit_ms"] for r in published]),
        "worst_probe_error_mm": max((r["cumulative_geometry"]["probe_max_mm"] for r in published), default=None),
        "worst_uncut_sample_error_mm": max((r["preservation"]["uncut_sampled_max_mm"] for r in published), default=None),
        "continuous_geometry_certified": False}
    for region in ("quality_all", "quality_sweep_margin_roi"):
        quality = [r["preservation"][region] for r in published]
        result[region] = {"median_faces": median([q["total_faces"] for q in quality]),
            "median_high_quality_face_percent": median([q["high_quality_25_deg_q_0_4"]["fraction"] * 100
                for q in quality if q["high_quality_25_deg_q_0_4"]["fraction"] is not None]),
            "median_high_quality_area_percent": median([q["high_quality_25_deg_q_0_4"]["area_fraction"] * 100
                for q in quality if q["high_quality_25_deg_q_0_4"]["area_fraction"] is not None]),
            # 空扫掠邻域没有质量分母，保持缺失而不是填为零小角比例。
            "nonempty_region_frames": sum(q["total_faces"] > 0 for q in quality),
            "angle_statistics": {str(a): {
                "median_face_percent": median([q[f"angle_below_{a}_deg"]["fraction"] * 100 for q in quality
                    if q[f"angle_below_{a}_deg"]["fraction"] is not None]),
                "median_area_percent": median([q[f"angle_below_{a}_deg"]["area_fraction"] * 100 for q in quality
                    if q[f"angle_below_{a}_deg"]["area_fraction"] is not None])}
                for a in (10, 5, 1)}}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ledger_path = args.output / "01-全范围冻结与执行账本.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    result = {"time_beijing": now(), "ledger_sha256": sha256(ledger_path),
        "manifest_sha256": sha256(manifest_path), "ledger_status": ledger["status"], "stages": {},
        "scope": "路线为独立统计单位；发布帧指标不含被阻断帧，失败分母另外完整报告"}
    for split in ("long", "application", "evaluation"):
        routes = [r for r in manifest["routes"] if r["split"] == split]
        path = args.output / split / "01-反馈执行与独立审计.json"
        planned = sum(len(r["cutting_prefix_ids"]) for r in routes)
        item = {"planned_routes": len(routes), "planned_cutting_events_per_branch": planned}
        result["stages"][split] = item
        if not path.exists():
            item["status"] = "not_executed"
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        item.update(status=record["status"], record_sha256=sha256(path), branches={}, routes=[])
        for branch in ("full", "candidate"):
            rows = [r for r in record["rows"] if r["branch"] == branch]
            item["branches"][branch] = distributions(rows)
        for route in routes:
            route_item = {"route": route["id"], "planned_events": len(route["cutting_prefix_ids"]), "branches": {}}
            for branch in ("full", "candidate"):
                rows = [r for r in record["rows"] if r["branch"] == branch and r["route"] == route["id"]]
                route_item["branches"][branch] = {"statuses": dict(Counter(r["status"] for r in rows)),
                    "all_events_covered": len(rows) == len(route["cutting_prefix_ids"]) and all(r["status"] in
                        ("published_under_sampled_and_vertex_protocol", "contained_reused_parent") for r in rows)}
            item["routes"].append(route_item)
        # 同前缀均发布的对子只支持该有效子集，不把筛选后配对当作整组优势。
        baseline = {(r["route"], r["event"]): r for r in record["rows"] if r["branch"] == "full"
                    and r["status"] == "published_under_sampled_and_vertex_protocol"}
        pairs = [(r, baseline[(r["route"], r["event"])]) for r in record["rows"] if r["branch"] == "candidate"
            and r["status"] == "published_under_sampled_and_vertex_protocol" and (r["route"], r["event"]) in baseline]
        item["valid_prefix_pair_count"] = len(pairs)
        item["paired_angle10_percentage_point_change_median"] = {region: median([
            (r["preservation"][region]["angle_below_10_deg"]["fraction"] -
             b["preservation"][region]["angle_below_10_deg"]["fraction"]) * 100 for r, b in pairs
             if r["preservation"][region]["angle_below_10_deg"]["fraction"] is not None
             and b["preservation"][region]["angle_below_10_deg"]["fraction"] is not None])
             for region in ("quality_all", "quality_sweep_margin_roi")}
    feature_path = args.output / "features" / "02-浅磨特征保持审计.json"
    features = {"planned_features": len(manifest["negative_inputs"]), "status": "not_executed"}
    if feature_path.exists():
        record = json.loads(feature_path.read_text(encoding="utf-8"))
        features.update(status=record["status"], record_sha256=sha256(feature_path),
            method_status_counts={method: dict(Counter(r["status"] for r in record["rows"] if r.get("method") == method))
                for method in ("full", "spatial", "boolean")})
    result["stages"]["features"] = features
    save(args.output / "04-全范围路线与质量误差统计.json", result)
    print(json.dumps({"status": result["ledger_status"], "stages": {
        name: {"status": value["status"], "planned_routes": value.get("planned_routes")}
        for name, value in result["stages"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
