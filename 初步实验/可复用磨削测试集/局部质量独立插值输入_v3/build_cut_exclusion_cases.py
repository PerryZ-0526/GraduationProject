"""新增均匀插值参数的保留几何体，并把仿真交叉运动锚定在实际输入表面。"""

import argparse
from pathlib import Path
import shutil

import numpy as np

from build_cases import make_body, digest
from prepare_feedback import make_route, save_obj_fp64
from datetime import datetime
from zoneinfo import ZoneInfo
import json


def build(output,parameters=(.5,1.5,2.5,3.5)):
    # 显式新参数只生成新目录；原默认参数、旧资产及划分保持不变。
    parameters=tuple(parameters)
    if not parameters or len(set(parameters)) != len(parameters) or not all(np.isfinite(p) and 0 <= p <= 4 for p in parameters):
        raise ValueError("参数必须唯一、有限且位于原家族0至4的参数域")
    inputs = output / "inputs"
    inputs.mkdir(parents=True, exist_ok=False)
    report = {"生成时间": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "修改时间及修改内容": "首次生成，旧版本和已见评价结果保留",
              "文档概述": f"七家族各{len(parameters)}个参数几何体，{7*len(parameters)}体三段交叉仿真路线；算法评价身份另行登记",
              "索引目录": ["generation_rule", "bodies", "routes"],
              "generation_rule": {"parameters": list(parameters), "distribution": "与v1同参数家族的显式插值，不是新患者或新分布",
                                  "anchor": "面心z最高的输入三角面，工具中心沿其外法向偏移0.35倍半径",
                                  "span": "两个正交切向方向各正负1.5倍工具半径"},
              "routes": [], "bodies": [], "negative_inputs": [], "units": {"length": "mm", "time": "ms"},
              "replay_policy": {"late_event": "reject", "max_link_gap_ms": 200},
              "source_hashes": {name: digest(Path(__file__).with_name(name)) for name in
                                ("build_cut_exclusion_cases.py", "build_cases.py", "prepare_feedback.py")}}
    for family in ("板体", "球体", "椭球", "弯曲骨样体", "贯通孔", "薄壁", "窄缝"):
        for parameter in parameters:
            mesh = make_body(family, parameter)
            # 保留旧默认编号，新参数采用实际数值编码，避免整数截断造成身份碰撞。
            suffix=f"{int(parameter * 10):02d}" if parameters==(.5,1.5,2.5,3.5) else format(parameter,".17g").replace(".","p")
            body_id = f"{family}_新参数{suffix}"
            path = inputs / f"{body_id}.obj"
            save_obj_fp64(mesh, path)
            face = int(np.argmax(mesh.triangles_center[:, 2]))
            anchor, normal = mesh.triangles_center[face], mesh.face_normals[face]
            radius = min(.6, float(np.min(mesh.extents)) * .4)
            axis = np.eye(3)[int(np.argmin(np.abs(normal)))]
            tangent = np.cross(normal, axis)
            tangent /= np.linalg.norm(tangent)
            second = np.cross(normal, tangent)
            center = anchor + normal * radius * .35
            points = np.array([center + radius * 1.5 * (x * tangent + y * second)
                               for x, y in ((-1, -1), (1, 1), (-1, 1), (1, -1))])
            motion = {"tool_radius_mm": radius,
                      "events": [{"position_mm": point.tolist()} for point in points]}
            body = {"id": body_id, "parameter": parameter, "family": family, "mesh": path.name,
                    "sha256": digest(path), "anchor_face": face, "anchor_mm": anchor.tolist(),
                    "normal": normal.tolist(), "unit": "人为毫米测试尺度", "split": "held_out_for_v2"}
            route = make_route(body, "交叉", motion, path, inputs, "evaluation", "synthetic_new_parameter_v2")
            route["initial_surface_anchor"] = {"face": face, "point_mm": anchor.tolist(), "normal": normal.tolist()}
            report["bodies"].append(body)
            report["routes"].append(route)
    for name in report["source_hashes"]:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    (output / "01-完整范围冻结清单.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parameters",type=float,nargs="+",default=[.5,1.5,2.5,3.5])
    args = parser.parse_args()
    report = build(args.output,args.parameters)
    print(json.dumps({"bodies": len(report["bodies"]), "routes": len(report["routes"]),
                      "tools": sum(len(r["prefix_tools"]) for r in report["routes"])}, ensure_ascii=False))
