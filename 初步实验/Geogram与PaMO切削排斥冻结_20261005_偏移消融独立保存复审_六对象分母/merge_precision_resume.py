"""合并同一冻结版本的完整路线记录，保留原失败，不合并性能分布。"""
import argparse
from collections import Counter
import json
from pathlib import Path
from verify_precision_resume import digest, partition, read, verify


def combine(original, remaining, prior, resumed):
    """续跑必须终态且覆盖剩余完整路线，方法与原记录一致。"""
    if resumed["status"] != "completed_with_recorded_failures":
        raise ValueError("续跑没有取得完整终态")
    partition(original, remaining, prior["rows"])
    partition(remaining, {"routes": []}, resumed["rows"])
    old_environment = prior["environment"]
    new_environment = resumed["environment"]
    # 环境包含不同设备与计时；只核对列明方法及作者二进制，不混合耗时。
    fields = [key for key in old_environment if key.endswith("sha256") and key != "executable_sha256"]
    for key in fields:
        if old_environment[key] != new_environment.get(key):
            raise ValueError("续跑方法摘要与旧版本不同：" + key)
    if old_environment["device"]["extension_sha256"] != new_environment["device"]["extension_sha256"]:
        raise ValueError("续跑作者扩展不同")
    rows = prior["rows"] + resumed["rows"]
    counts = {branch: dict(Counter(row["status"] for row in rows if row["branch"] == branch))
              for branch in ("R", "full", "candidate")}
    completed = {}
    for branch in ("full", "candidate"):
        completed[branch] = sum(all(row["status"] in
            ("published_under_sampled_and_vertex_protocol", "contained_reused_parent")
            for row in rows if row["route"] == route["id"] and row["branch"] == branch)
            for route in original["routes"])
    return {"status": "completed_with_recorded_failures", "total_routes": len(original["routes"]), "total_events": len(rows) // 3,
            "rows": rows, "status_counts": counts, "complete_routes": completed,
            "devices": [old_environment["device"], new_environment["device"]],
            "scope": "完整记录分母和方法一致性；不替代保存网格复审，不合并不同设备性能"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--resumed-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verification = verify(args.prepared, Path(__file__).parent)
    protocol = read(args.prepared / "02-断连续跑协议.json")
    prior_root = Path(protocol["prior_output"])
    old_path = prior_root / "01-反馈执行与独立审计.json"
    new_path = args.resumed_output / old_path.name
    remaining_path = args.prepared / "01-完整范围冻结清单.json"
    original = read(Path(protocol["parent_prepared"]) / remaining_path.name)
    resumed = read(new_path)
    if resumed["manifest_sha256"] != digest(remaining_path):
        raise ValueError("续跑执行记录的输入清单摘要不同")
    result = combine(original, read(remaining_path), read(old_path), resumed)
    if result["total_events"] != protocol["original_planned_events"]:
        raise ValueError("合并后完整分母不同")
    result.update(time_beijing=verification["time_beijing"], source_records=[
        {"path": str(path.resolve()), "sha256": digest(path)} for path in (old_path, new_path)])
    # 保存各行所属原目录，避免合并后丢失其实际网格位置。
    for row, root in [(row, prior_root) for row in read(old_path)["rows"]] + [(row, args.resumed_output) for row in resumed["rows"]]:
        match = next(item for item in result["rows"] if (item["route"], item["event"], item["branch"]) ==
                     (row["route"], row["event"], row["branch"]))
        match["source_output_directory"] = str(root.resolve())
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(result["total_events"], result["complete_routes"], result["status_counts"])


if __name__ == "__main__":
    main()
