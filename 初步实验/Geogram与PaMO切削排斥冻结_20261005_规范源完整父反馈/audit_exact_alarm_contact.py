"""只读复核切平面开发报警，保留历史拒绝，不替代完整自交检测。"""
import json
from pathlib import Path
import numpy as np
import pymeshlab as pm
import trimesh
from exact_alarm_contact import prove_contact
from geometry_preservation_audit import triangle_separation_gap
from audit_followup_candidate import sha256
from run_geometry_study import now


def main():
    root = Path(__file__).parent / "实验结果/20261004_切平面约束公开肩胛骨开发"
    rows = []
    for path in root.rglob("candidate.obj"):
        mesh = trimesh.load(path, process=False)
        detector = pm.MeshSet()
        detector.add_mesh(pm.Mesh(mesh.vertices, mesh.faces))
        detector.compute_selection_by_self_intersections_per_face()
        ids = np.flatnonzero(detector.current_mesh().face_selection_array())
        pairs = []
        for n, first in enumerate(ids):
            for second in ids[n+1:]:
                if triangle_separation_gap(mesh.triangles[first], mesh.triangles[second]) <= 1e-9:
                    pairs.append(dict(faces=[int(first), int(second)],
                        **prove_contact(mesh.vertices, mesh.faces[first], mesh.faces[second])))
        rows.append(dict(case=path.parent.name, mesh_sha256=sha256(path), raw_alarm_faces=len(ids),
            pairs=pairs, unresolved_pairs=sum(not p["proved"] for p in pairs)))
        print(path.parent.name, rows[-1]["unresolved_pairs"])
    result = dict(time_beijing=now(), rows=rows, code_sha256=sha256(Path(__file__).with_name("exact_alarm_contact.py")),
        scope="仅复核给定报警集合；不认证全网格无自交；旧拒绝保留")
    (root / "03-精确共享接触候选轴复核.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
