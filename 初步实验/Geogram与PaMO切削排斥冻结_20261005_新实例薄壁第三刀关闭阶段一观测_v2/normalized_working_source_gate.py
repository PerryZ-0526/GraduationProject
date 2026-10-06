"""完整求解前核对实际工作源，只整理SDF有向面链，不改变碰撞源。"""

import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone, timedelta

import numpy as np
import torch
import pamo
from normalized_sdf_chain import canonical_normalized_chain


def install_working_source_gate(output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    checker = Path("/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646")
    if hashlib.sha256(checker.read_bytes()).hexdigest() != "0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3":
        raise ValueError("实际工作源检查器摘要改变")
    original = pamo.PaMO.preprocess_mesh

    def preprocess(self, points, triangles, band, margin):
        normalized, minimum, maximum, mean = original(self, points, triangles, band, margin)
        indices = triangles.cpu().numpy()
        # 初始编码与再中心化均从实际CUDA张量读回，禁止用CPU模拟替代输入证据。
        initial = points.cpu().numpy()
        centered = (points - torch.from_numpy(mean).to(points.device)).cpu().numpy()
        vertices, faces, cleaned, chain = canonical_normalized_chain(normalized)
        report = {"生成时间": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                  "修改时间及修改内容": "首次生成，完整求解前验证三份实际工作源",
                  "文档概述": "只整理归一化SDF有向面链，原碰撞面及其坐标保持",
                  "索引目录": ["chain", "checks"], "chain": chain, "checks": [], "status": "checking"}
        record = output / "04-完整求解前实际工作源门控.json"
        for name, xyz, face in [("01-CUDA初始编码源.obj", initial, indices),
                                ("02-CUDA再中心化碰撞源.obj", centered, indices),
                                ("03-整理后归一化SDF源.obj", vertices, faces)]:
            path = output / name
            # 不作容差焊接，17位数字精确绑定实际送入计算的浮点对象。
            with path.open("w", encoding="utf8") as stream:
                for vertex in xyz:
                    stream.write("v " + " ".join(format(float(x), ".17g") for x in vertex) + "\n")
                for triangle in face:
                    stream.write("f " + " ".join(str(int(x) + 1) for x in triangle) + "\n")
            run = subprocess.run([str(checker), str(path)], capture_output=True, text=True, check=True)
            check = json.loads(run.stdout)
            row = {"file": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "embedding": check}
            report["checks"].append(row)
            report["status"] = "checking" if check["embedded_closed"] else "rejected_before_full_solver"
            record.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf8")
            if not check["embedded_closed"]:
                raise RuntimeError("实际工作源未通过完整闭合嵌入检查：" + name)
        # 作者随后按原始目标面数选择128/64/256，面链整理不改变该目标或坐标变换。
        report.update(status="passed_before_full_solver", collision_faces_changed=False,
                      original_source_faces=len(indices), SDF_faces=len(faces),
                      author_resolution_expected=64 if len(indices) <= 50 else 128 if len(indices) <= 1000 else 256)
        record.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf8")
        return cleaned, minimum, maximum, mean

    pamo.PaMO.preprocess_mesh = preprocess
