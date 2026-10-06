"""统一仿真运动记录、在线回放规则与解析材料状态。"""
from pathlib import Path
import json

import numpy as np


HERE = Path(__file__).resolve().parent


class RecordError(ValueError):
    """记录缺少必要信息或违反明确回放规则。"""


def load_document(path=HERE / "cases.json"):
    """读取并校验共同试题。"""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_document(document)
    return document


def validate_document(document):
    """拒绝单位、坐标、时间或运动连接含糊的输入。"""
    if document.get("schema_version") != 1:
        raise RecordError("只支持schema_version=1")
    if document.get("record_kind") not in {"simulated", "recorded"}:
        raise RecordError("record_kind必须明确为simulated或recorded")
    frame = document.get("coordinate_frame", {})
    if frame != {
        "name": "bone",
        "length_unit": "mm",
        "time_unit": "ms",
        "handedness": "right",
    }:
        raise RecordError("本批试题必须显式使用右手骨坐标、毫米和毫秒")
    policy = document.get("replay_policy", {})
    if policy.get("late_event") != "reject":
        raise RecordError("晚到数据必须显式拒绝，当前不支持回写已发布历史")
    if policy.get("interpolate_missing_motion") is not False:
        raise RecordError("禁止静默补齐缺失运动")
    if not isinstance(policy.get("max_link_gap_ms"), (int, float)) or policy["max_link_gap_ms"] <= 0:
        raise RecordError("max_link_gap_ms必须为正")

    case_ids = set()
    for case in document.get("cases", []):
        case_id = case.get("id")
        if not case_id or case_id in case_ids:
            raise RecordError("案例id必须非空且唯一")
        case_ids.add(case_id)
        if case.get("split") not in {"development", "evaluation"}:
            raise RecordError(f"{case_id}: split必须区分development和evaluation")
        surface = case.get("initial_surface", {})
        if surface.get("kind") != "plane":
            raise RecordError(f"{case_id}: 本批只接受有解析答案的平面")
        coefficients = np.asarray(surface.get("height_coefficients"), dtype=np.float64)
        if coefficients.shape != (3,) or not np.isfinite(coefficients).all():
            raise RecordError(f"{case_id}: 初始平面系数不合法")
        plan = case.get("plan", {})
        center = np.asarray(plan.get("center_xy_mm"), dtype=np.float64)
        if center.shape != (2,) or not np.isfinite(center).all() or plan.get("allowed_radius_mm", 0) <= 0:
            raise RecordError(f"{case_id}: 计划圆域不合法")
        target_depth = plan.get("target_depth_mm")
        if target_depth is not None and (
            not isinstance(target_depth, (int, float))
            or not np.isfinite(target_depth)
            or target_depth <= 0
        ):
            raise RecordError(f"{case_id}: 计划目标深度必须为正数")
        tool = case.get("tool", {})
        if tool.get("kind") != "sphere" or tool.get("radius_mm", 0) <= 0:
            raise RecordError(f"{case_id}: 本批只接受正半径球形磨钻")

        event_ids = set()
        for index, event in enumerate(case.get("events", [])):
            event_id = event.get("id")
            if not event_id or event_id in event_ids:
                raise RecordError(f"{case_id}: 事件id必须非空且唯一")
            event_ids.add(event_id)
            if event.get("arrival_index") != index:
                raise RecordError(f"{case_id}/{event_id}: arrival_index必须反映实际到达顺序")
            if not isinstance(event.get("timestamp_ms"), (int, float)):
                raise RecordError(f"{case_id}/{event_id}: 缺少时间戳")
            position = np.asarray(event.get("position_mm"), dtype=np.float64)
            quaternion = np.asarray(event.get("orientation_xyzw"), dtype=np.float64)
            if position.shape != (3,) or not np.isfinite(position).all():
                raise RecordError(f"{case_id}/{event_id}: 位置不合法")
            if quaternion.shape != (4,) or not np.isfinite(quaternion).all():
                raise RecordError(f"{case_id}/{event_id}: 姿态不合法")
            if abs(np.linalg.norm(quaternion) - 1.0) > 1e-12:
                raise RecordError(f"{case_id}/{event_id}: 姿态四元数未归一化")
            if not isinstance(event.get("cutting"), bool) or not isinstance(
                event.get("connect_from_previous"), bool
            ):
                raise RecordError(f"{case_id}/{event_id}: 切削和连接标记必须为布尔值")
        if not event_ids:
            raise RecordError(f"{case_id}: 至少需要一个运动事件")


def replay_case(case, policy, through_event_id=None):
    """按到达顺序回放；晚到数据不改写历史，停钻后不自动连接。"""
    events = case["events"]
    if through_event_id is not None:
        positions = [i for i, event in enumerate(events) if event["id"] == through_event_id]
        if not positions:
            raise RecordError(f"{case['id']}: 未找到前缀事件{through_event_id}")
        events = events[: positions[0] + 1]

    accepted = []
    late = []
    primitives = []
    connected_segments = 0
    previous = None
    last_timestamp = None
    radius = float(case["tool"]["radius_mm"])
    for event in events:
        timestamp = float(event["timestamp_ms"])
        if last_timestamp is not None and timestamp <= last_timestamp:
            late.append(event["id"])
            continue
        if event["connect_from_previous"]:
            if previous is None or not previous["cutting"]:
                raise RecordError(
                    f"{case['id']}/{event['id']}: 不能跨停钻或缺失起点连接运动"
                )
            if timestamp - float(previous["timestamp_ms"]) > policy["max_link_gap_ms"]:
                raise RecordError(
                    f"{case['id']}/{event['id']}: 连接时间间隔超过显式上限"
                )
        accepted.append(event["id"])
        if event["cutting"]:
            end = np.asarray(event["position_mm"], dtype=np.float64)
            if event["connect_from_previous"]:
                start = np.asarray(previous["position_mm"], dtype=np.float64)
                connected_segments += 1
                connected = True
            else:
                start = end.copy()
                connected = False
            primitives.append(
                {
                    "event_id": event["id"],
                    "start": start,
                    "end": end,
                    "radius": radius,
                    "connected": connected,
                }
            )
        previous = event
        last_timestamp = timestamp
    return {
        "accepted_event_ids": accepted,
        "late_event_ids": late,
        "primitives": primitives,
        "connected_segment_count": connected_segments,
    }


def initial_field(points, case):
    """负值表示点位于初始骨材料内部。"""
    points = np.asarray(points, dtype=np.float64)
    a, b, offset = case["initial_surface"]["height_coefficients"]
    return points[..., 2] - (a * points[..., 0] + b * points[..., 1] + offset)


def plan_field(points, case):
    """负值表示点的水平位置位于计划允许圆域内。"""
    points = np.asarray(points, dtype=np.float64)
    center = np.asarray(case["plan"]["center_xy_mm"], dtype=np.float64)
    return (
        np.linalg.norm(points[..., :2] - center, axis=-1)
        - float(case["plan"]["allowed_radius_mm"])
    )


def capsule_field(points, primitive):
    """负值表示点位于一次球形磨钻扫掠内部。"""
    points = np.asarray(points, dtype=np.float64)
    start = primitive["start"]
    delta = primitive["end"] - start
    squared = float(delta @ delta)
    t = (
        np.zeros(points.shape[:-1])
        if squared == 0
        else np.clip(np.sum((points - start) * delta, axis=-1) / squared, 0.0, 1.0)
    )
    nearest = start + t[..., None] * delta
    return np.linalg.norm(points - nearest, axis=-1) - primitive["radius"]


def motion_field(points, replay):
    """负值表示至少被一段实际切削运动覆盖。"""
    points = np.asarray(points, dtype=np.float64)
    if not replay["primitives"]:
        return np.full(points.shape[:-1], np.inf)
    return np.min(
        np.stack([capsule_field(points, item) for item in replay["primitives"]]),
        axis=0,
    )


def actual_material_field(points, case, replay):
    """实际运动推算的剩余材料；计划边界不会静默截断实际运动。"""
    return np.maximum(initial_field(points, case), -motion_field(points, replay))


def planned_material_field(points, case, replay):
    """仅用于计划内目标比较：实际扫掠与计划圆域相交后再去除。"""
    planned_cut = np.maximum(motion_field(points, replay), plan_field(points, case))
    return np.maximum(initial_field(points, case), -planned_cut)


def classify_points(points, case, replay):
    """区分计划内去除、计划外实际去除、保留材料和初始骨外点。"""
    points = np.asarray(points, dtype=np.float64)
    base = initial_field(points, case)
    swept = motion_field(points, replay)
    plan = plan_field(points, case)
    margin = 1e-10
    if np.any(np.abs(np.stack([base, swept, plan])) <= margin):
        raise RecordError("预期答案探针不能放在材料或计划边界上")
    states = np.full(base.shape, "not_bone", dtype=object)
    inside = base < -margin
    states[inside & (swept > margin)] = "retained"
    states[inside & (swept < -margin) & (plan < -margin)] = "removed_within_plan"
    states[inside & (swept < -margin) & (plan > margin)] = "outside_plan_removed"
    return states


def sample_box(case, spacing=0.2):
    """固定范围的规则探针只用于不变量对拍，不作为曲面误差证书。"""
    events = np.asarray([event["position_mm"] for event in case["events"]], dtype=np.float64)
    radius = float(case["tool"]["radius_mm"])
    low = events.min(axis=0) - radius - 0.5
    high = events.max(axis=0) + radius + 0.5
    axes = [
        np.linspace(low[i], high[i], max(2, int(np.ceil((high[i] - low[i]) / spacing)) + 1))
        for i in range(3)
    ]
    return np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
