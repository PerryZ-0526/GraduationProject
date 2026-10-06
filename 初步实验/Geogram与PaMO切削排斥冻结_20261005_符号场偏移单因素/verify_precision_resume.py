"""只读核对断连续跑输入、已记录分母和当前精度机制，不能替代远端任务检查。"""
import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def partition(original, remaining, rows):
    """按完整路线切分，任何重复行、未知事件或半条路线均拒绝。"""
    routes = {route["id"]: route for route in original["routes"]}
    if len(routes) != len(original["routes"]):
        raise ValueError("原清单路线重复")
    pending = {route["id"]: route for route in remaining["routes"]}
    if len(pending) != len(remaining["routes"]):
        raise ValueError("续跑清单路线重复")
    for name, route in pending.items():
        if routes.get(name) != route:
            raise ValueError("续跑路线不等于原冻结输入")
    expected = {(name, event, branch) for name, route in routes.items()
                for event in route["cutting_prefix_ids"] for branch in ("R", "full", "candidate")}
    keys = [(row["route"], row["event"], row["branch"]) for row in rows]
    if len(keys) != len(set(keys)) or not set(keys) <= expected:
        raise ValueError("既有记录重复或存在未登记事件")
    done = set()
    for name, route in routes.items():
        wanted = {key for key in expected if key[0] == name}
        present = {key for key in keys if key[0] == name}
        if present and present != wanted:
            raise ValueError("既有记录包含半条路线，不能从初态重复续跑")
        if present:
            done.add(name)
    if set(pending) != set(routes) - done:
        raise ValueError("续跑路线遗漏或与已记录路线重叠")
    return {"recorded_routes": len(done), "remaining_routes": len(pending),
            "recorded_events": len(keys) // 3,
            "remaining_events": sum(len(route["cutting_prefix_ids"]) for route in pending.values()),
            "prior_status_counts": dict(Counter(row["status"] for row in rows))}


def verify(prepared, code_root):
    protocol = read(prepared / "02-断连续跑协议.json")
    prior = Path(protocol["prior_output"])
    record_path = prior / "01-反馈执行与独立审计.json"
    manifest_path = prepared / "01-完整范围冻结清单.json"
    original_path = Path(protocol["parent_prepared"]) / manifest_path.name
    for path, expected in ((record_path, protocol["interruption"]["original_record_sha256"]),
                           (manifest_path, protocol["remaining_manifest_sha256"])):
        if digest(path) != expected:
            raise ValueError("断连记录或续跑清单摘要变化")
    remaining = read(manifest_path)
    if digest(original_path) != remaining["continuation_parent_manifest_sha256"]:
        raise ValueError("原输入清单摘要变化")
    original = read(original_path)
    result = partition(original, remaining, read(record_path)["rows"])
    for key, field in (("recorded_events", "already_recorded_events"),
                       ("remaining_events", "remaining_planned_events")):
        if result[key] != protocol[field]:
            raise ValueError("协议事件分母不一致")
    if result["recorded_events"] + result["remaining_events"] != protocol["original_planned_events"]:
        raise ValueError("完整事件分母不一致")
    # 每张续跑初态和工具均重新读文件验证，不依赖复制成功的假设。
    checked = 0
    for route in remaining["routes"]:
        files = [(route["initial_mesh"], route["initial_mesh_sha256"])]
        files += [(tool["mesh"], tool["sha256"]) for tool in route["prefix_tools"]]
        for name, expected in files:
            if digest(prepared / "inputs" / name) != expected:
                raise ValueError("续跑几何文件摘要变化")
            checked += 1
    environment = read(prior / "02-本批方法冻结.json")["environment"]
    code_checked = 0
    for group in ("precision_code_sha256", "opposed_pair_code_sha256", "small_incident_code_sha256",
                  "shared_repair_sha256", "local_recovery_code_sha256", "planar_code_sha256"):
        for name, expected in environment[group].items():
            if digest(code_root / name) != expected:
                raise ValueError("当前方法与断连版本不同：" + name)
            code_checked += 1
    for name, field in (("collision_protected_gpu.py", "collision_protected_gpu_sha256"),
                        ("exact_alarm_contact.py", "exact_contact_audit_sha256")):
        if digest(code_root / name) != environment[field]:
            raise ValueError("当前保护或审计与断连版本不同：" + name)
        code_checked += 1
    # 用实际入口的同一导入替换规则检查生成内核，避免仅检查模板。
    worker = (code_root / "run_planar_worker.py").read_text(encoding="utf-8")
    marker = "from collision_protected_gpu import CollisionProtectedSystem"
    if worker.count(marker) != 1:
        raise ValueError("精度工作进程模板导入不唯一")
    generated = worker.replace(marker, "from precision_collision_system import CollisionProtectedSystem")
    if hashlib.sha256(generated.replace("\n", os.linesep).encode("utf-8")).hexdigest() != environment["actual_precision_worker_sha256"]:
        raise ValueError("实际精度工作进程与断连版本不同")
    result.update(time_beijing=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                  checked_input_files=checked, checked_code_entries=code_checked,
                  scope="本机输入及列明方法摘要核对；远端进程、二进制、环境和保存网格需另行核查")
    return result


def preflight(argv, code_root):
    """存在续跑协议时强制检查完整子集，普通批次仍使用原入口。"""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--split")
    args, _ = parser.parse_known_args(argv)
    if args.prepared is None or not (args.prepared / "02-断连续跑协议.json").exists():
        return None
    manifest = read(args.prepared / "01-完整范围冻结清单.json")
    if {route["split"] for route in manifest["routes"]} != {args.split}:
        raise ValueError("续跑split必须覆盖整个冻结剩余清单")
    return verify(args.prepared, code_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.prepared, Path(__file__).parent), ensure_ascii=False, indent=2))
