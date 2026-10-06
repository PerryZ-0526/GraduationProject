"""只读保存薄壁完整GPU的三个阶段，恢复同一个均值及世界原点。"""

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pamo
import pamo_safe_project
import trimesh


def install_stage_observation(output, origin):
    output = Path(output)
    output.mkdir(exist_ok=False)
    origin = np.asarray(origin, np.float64)
    record = {"role": "observational_readbacks_not_performance_evidence", "rows": []}
    checker = "/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646"
    assert hashlib.sha256(Path(checker).read_bytes()).hexdigest() == "0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3"

    def capture(name, vertices, faces):
        mesh = trimesh.Trimesh(np.asarray(vertices, np.float64) + origin, faces, process=False)
        path = output / (name + ".obj")
        with path.open("w", encoding="utf8") as stream:
            for point in mesh.vertices:
                stream.write("v " + " ".join(format(float(x), ".17g") for x in point) + "\n")
            for face in mesh.faces:
                stream.write("f " + " ".join(str(int(i) + 1) for i in face) + "\n")
        check = subprocess.run([checker, str(path)], check=True, capture_output=True, text=True)
        record["rows"].append({"stage": name, "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "vertices": len(mesh.vertices),
            "faces": len(mesh.faces), "volume_mm3": float(mesh.volume),
            "bounds_mm": mesh.bounds.tolist(), "embedding": json.loads(check.stdout)})
        (output / "01-薄壁同次完整GPU三阶段保存.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), "utf8")

    remesh = pamo.PaMO.remesh

    def observed_remesh(self, tris, minimum, maximum, mean):
        vertices, faces = remesh(self, tris, minimum, maximum, mean)
        # 后续预算对照核对实际简化输入张量，保存坐标恢复前的FP32逐位数组。
        np.savez_compressed(output / "stage1_centered.npz", vertices=vertices.detach().cpu().numpy(),
                            faces=faces.detach().cpu().numpy(), mean=mean)
        # 与作者阶段二出口相同的FP32均值恢复；世界原点最后以FP64加回。
        capture("stage1", vertices.detach().cpu().numpy() + mean, faces.detach().cpu().numpy())
        return vertices, faces

    process = pamo_safe_project.process

    def observed_process(gt_vertices, gt_faces, vertices, faces, *args, **kwargs):
        # 记录作者实际交接对象，原投影参数及返回对象保持原样。
        capture("stage2", vertices, faces)
        result = process(gt_vertices, gt_faces, vertices, faces, *args, **kwargs)
        capture("stage3", result[0], result[1])
        return result

    pamo.PaMO.remesh = observed_remesh
    pamo_safe_project.process = observed_process
