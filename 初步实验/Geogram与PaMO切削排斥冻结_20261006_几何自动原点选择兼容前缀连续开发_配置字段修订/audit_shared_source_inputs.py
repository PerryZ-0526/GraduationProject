"""只读验证上批共同来源阻断帧，两侧几何都核对，不改写保存标签。"""
import json
from pathlib import Path
import numpy as np
import trimesh
from locality_diagnostic import source_region, verify_labels
from locality_cleanup import clean_provenance
from audit_followup_candidate import sha256
from run_geometry_study import now


def main():
    here = Path(__file__).parent
    root = here / "实验结果/20261004_切空间与精确接触公开骨面反馈_v2"
    prepared = here.parent / "可复用磨削测试集/公开浅磨批次_v2"
    manifest = json.loads((prepared / "01-完整范围冻结清单.json").read_text(encoding="utf-8"))
    routes = {x["id"]: x for x in manifest["routes"]}
    report = json.loads((root / "01-反馈执行与独立审计.json").read_text(encoding="utf-8"))
    rows = []
    for row in report["rows"]:
        if row["status"] != "source_cleanup_rejected":
            continue
        inputs = root / (row["route"] + "_" + row["event"] + "_candidate_input")
        mesh = trimesh.load(inputs / "source.obj", process=False)
        bits = np.array(json.loads((inputs / "labels.json").read_text())["operand_bits"])
        parent_path = root / (row["route"] + "_e0_candidate_boolean") / "candidate.obj"
        parent = trimesh.load(parent_path, process=False)
        tool_info = next(x for x in routes[row["route"]]["prefix_tools"] if x["event_id"] == row["event"])
        tool = trimesh.load(prepared / "inputs" / tool_info["mesh"], process=False)
        cleaned, labels, details = clean_provenance(mesh, bits, allow_shared=True)
        _, _, seam = source_region(cleaned, labels, allow_shared=True)
        check = verify_labels(cleaned, labels, parent, tool, seam, allow_shared=True)
        rows.append(dict(route=row["route"], shared_faces=int((labels == 3).sum()), source_sha256=sha256(inputs / "source.obj"),
            parent_sha256=sha256(parent_path), expected_parent_sha256=row["parent_sha256"], check=check, cleanup=details))
        print(row["route"], rows[-1]["shared_faces"], check["passed_1e_8_mm_numerical_check"])
    (root / "05-共同来源双表面只读核对.json").write_text(json.dumps(dict(time_beijing=now(), rows=rows),ensure_ascii=False,indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
