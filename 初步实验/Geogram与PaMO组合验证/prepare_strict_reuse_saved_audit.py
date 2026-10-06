"""独立冻结保存复审入口，显式区分GPU提案证据与严格无变化复用证据。"""

import hashlib
import json
from pathlib import Path
import shutil


def main():
    here = Path(__file__).resolve().parent
    old = here.parent / "Geogram与PaMO切削排斥冻结_20261005_分布观察控制与复审"
    output = here.parent / "Geogram与PaMO切削排斥冻结_20261005_严格复用保存独立复审"
    output.mkdir(exist_ok=False)
    text = (old / "audit_distribution_observation_outputs.py").read_text("utf8")
    text = text.replace('import trimesh\n', 'import trimesh\nfrom exact_oriented_surface_identity import exact_oriented_surface_identity\n', 1)
    text = text.replace('        parents = {', '        parent_paths = {r["id"]: args.prepared / "inputs" / r["initial_mesh"] for r in routes.values()}\n        parents = {', 1)
    start = text.index('                details = row["attempt"]["cut_exclusion"]')
    end = text.index('                path = args.batch', start)
    gpu = text[start:end]
    text = text[:start] + '''                reuse = row.get("execution_role") == "strict_no_change_reuse"
                identity_passed = True
                if reuse:
                    details = {"cumulative_tool_sha256": [x["tool_sha256"] for x in row["attempt"]["cumulative_tools"]],
                               "cumulative_reference_sha256": row["reference_sha256"]}
                    source_folder = args.batch / f"{rid}_{event}_candidate_input"
                    prior = trimesh.load(parent_paths[rid], force="mesh", process=False)
                    for mesh_name, labels_name in (("source.obj", "labels.json"), ("clean_source.obj", "clean_labels.json")):
                        source = trimesh.load(source_folder / mesh_name, force="mesh", process=False)
                        bits = json.loads((source_folder / labels_name).read_text("utf8"))["operand_bits"]
                        identity_passed = identity_passed and exact_oriented_surface_identity(prior, source, bits)["same"]
                    identity_passed = identity_passed and sha256(parent_paths[rid]) == row["output_sha256"]
                else:
''' + ''.join('    ' + line if line.strip() else line for line in gpu.splitlines(keepends=True)) + text[end:]
    text = text.replace('                parents[rid] = row["output_sha256"]', '                parents[rid] = row["output_sha256"]\n                parent_paths[rid] = path')
    old_line = '            selections = details["attempts"][details["selected_level"]]["exclusion"]["frozen_face_support_ids"]'
    new_line = '''            if reuse:
                shift = 0
                selections = []
                for certificate, (n, b) in zip(row["attempt"]["cumulative_tools"], planes):
                    selections.append(np.asarray(certificate["face_support_ids"]) + shift)
                    shift += len(n)
            else:
                selections = details["attempts"][details["selected_level"]]["exclusion"]["frozen_face_support_ids"]'''
    assert text.count(old_line) == 1
    text = text.replace(old_line, new_line)
    text = text.replace('entry["passed"] = bool(valid and parent_matches', 'entry["identity_passed"] = identity_passed\n            entry["execution_role"] = row.get("execution_role", "full_GPU_and_correction")\n            entry["passed"] = bool(valid and parent_matches and identity_passed')
    text = text.replace('row["attempt"]["inputs_sha256"]["source.obj"]', '(row["attempt"]["audited_source_sha256"] if reuse else row["attempt"]["inputs_sha256"]["source.obj"])')
    text = text.replace('row["attempt"]["inputs_sha256"]["labels.json"]', '(row["attempt"]["audited_labels_sha256"] if reuse else row["attempt"]["inputs_sha256"]["labels.json"])')
    # 新入口仅支持本轮完整统一批次，不宣称其他历史输入分支经过验证。
    text = text.replace('    args = parser.parse_args()', '    args = parser.parse_args()\n    if args.kind != "unified":\n        raise ValueError("严格复用复审仅支持统一完整批次")')
    (output / "audit_strict_reuse_outputs.py").write_text(text, "utf8")
    shutil.copyfile(here / "exact_oriented_surface_identity.py", output / "exact_oriented_surface_identity.py")
    rows = [{"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(output.glob("*.py"))]
    (output / "01-执行源码冻结清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf8")
    print(output, flush=True)


if __name__ == "__main__":
    main()
