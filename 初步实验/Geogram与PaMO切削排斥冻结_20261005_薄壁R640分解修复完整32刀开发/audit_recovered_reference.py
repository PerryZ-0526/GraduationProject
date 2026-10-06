"""独立重放原始参照的清理与碎片修复，再核对保存的未发布候选。"""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from locality_cleanup import clean_provenance
from fragment_pipeline import repair_input
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_feedback import global_geometry
from locality_masks import save_obj_fp64
from audit_followup_candidate import sha256
from run_geometry_study import now


def main():
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=here / "实验结果/20261004_公开右肱骨累计参照恢复")
    parser.add_argument("--prior",type=Path,default=here / "实验结果/20261004_共同来源碎片修复公开骨面反馈")
    parser.add_argument("--route",default="BP3D_FJ3368_交叉浅磨")
    parser.add_argument("--event",default="e3")
    args = parser.parse_args()
    root, prior = args.root, args.prior
    path = root / "sequential_from_initial.obj"
    raw = trimesh.load(path,process=False)
    # 统一标签只表示待审参照整体，不冒充Geogram操作数来源；操作仍检查局部平面。
    clean, labels, cleanup = clean_provenance(raw,np.ones(len(raw.faces),int))
    repaired, _, repair = repair_input(clean,labels,audit=mesh_valid_exact_contacts)
    raw_geometry = global_geometry(repaired,raw)
    valid = repair["accepted"] and raw_geometry["probe_max_mm"] <= 1e-7
    save_obj_fp64(repaired,root / "sequential_repaired_reference.obj")
    checks=[]
    for method in ("boolean","expanded"):
        candidate_path = prior / (args.route+"_"+args.event+"_candidate_"+method) / "candidate.obj"
        candidate = trimesh.load(candidate_path,process=False)
        candidate_valid, metrics = mesh_valid_exact_contacts(candidate)
        geometry = global_geometry(candidate,repaired)
        checks.append(dict(method=method,sha256=sha256(candidate_path),valid=candidate_valid,metrics=metrics,
                           geometry=geometry,passed=bool(valid and candidate_valid and geometry["probe_max_mm"] <= .1)))
    result = dict(time_beijing=now(),route=args.route,event=args.event,raw_sha256=sha256(path),raw_metrics=dict(watertight=raw.is_watertight,euler_number=raw.euler_number),
        cleanup=cleanup,repair=repair,raw_to_repaired_geometry=raw_geometry,reference_valid=bool(valid),candidate_checks=checks,
        scope="独立初态及原工具序列，不借用维护父链；整体参照标签不代表操作数来源；只读补充不改写原未发布记录")
    (root / "02-原始重放参照修复与候选补充审计.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(valid,[(r["method"],r["passed"],r["geometry"]["probe_max_mm"]) for r in checks])


if __name__ == "__main__":
    main()
