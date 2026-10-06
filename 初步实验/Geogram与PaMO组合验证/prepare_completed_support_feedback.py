"""同级新快照只补复用支撑方向；独立复审重新证明全部新增工具支撑。"""

import hashlib
import json
from pathlib import Path
import shutil


def write_manifest(folder):
    rows = [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir()) if p.is_file() and p.name != "01-执行源码冻结清单.json"]
    (folder / "01-执行源码冻结清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf8")


def main():
    here = Path(__file__).resolve().parent
    old = here.parent / "Geogram与PaMO切削排斥冻结_20261005_倍率4薄壁三刀父反馈"
    output = here.parent / "Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈"
    output.mkdir(exist_ok=False)
    for row in json.loads((old / "01-执行源码冻结清单.json").read_text("utf8")):
        assert hashlib.sha256((old / row["file"]).read_bytes()).hexdigest() == row["sha256"]
        shutil.copyfile(old / row["file"], output / row["file"])
    text = (old / "strict_no_change_reuse.py").read_text("utf8")
    text = text.replace('from exact_oriented_surface_identity import', 'from face_normal_support_completion import complete_face_support\nfrom exact_oriented_surface_identity import', 1)
    original = '''        normals, offsets = supporting_planes(tool)
        selected, _ = face_separators(parent, tool)
        support = certify_face_support(parent, normals, offsets, selected)'''
    assert text.count(original) == 1
    text = text.replace(original, '        # 新方向须精确包含整个工具，再用于整面证明，物理顶点保持。\n        normals, offsets, selected, support, completion = complete_face_support(parent, tool)')
    text = text.replace('"face_support": support, "material_side": anchor', '"face_support": support, "material_side": anchor, "support_completion": completion')
    (output / "strict_no_change_reuse.py").write_text(text, "utf8")
    shutil.copyfile(here / "face_normal_support_completion.py", output / "face_normal_support_completion.py")
    driver = (old / "run_ratio4_thin_feedback.py").read_text("utf8")
    driver = driver.replace('simplification_target_ratio=4,', 'simplification_target_ratio=4, reuse_support="tool_face_normals_then_failed_triangle_own_normals_exact_tool_containment",')
    (output / "run_completed_support_feedback.py").write_text(driver, "utf8")
    write_manifest(output)
    oldqa = here.parent / "Geogram与PaMO切削排斥冻结_20261005_严格复用保存独立复审"
    qa = here.parent / "Geogram与PaMO切削排斥冻结_20261005_补充支撑独立保存复审"
    qa.mkdir(exist_ok=False)
    shutil.copyfile(oldqa / "exact_oriented_surface_identity.py", qa / "exact_oriented_surface_identity.py")
    text = (oldqa / "audit_strict_reuse_outputs.py").read_text("utf8")
    text = text.replace('import argparse\n', 'import argparse\nfrom fractions import Fraction\n', 1)
    marker = '            normals = np.concatenate([n for n, _ in planes])'
    assert text.count(marker) == 1
    extra = '''            added_plane_containment_passed = True
            if reuse:
                expanded = []
                for tool, (n, b), saved_certificate in zip(tools, planes, row["attempt"]["cumulative_tools"]):
                    for addition in saved_certificate["support_completion"]["added_planes"]:
                        normal = np.asarray(addition["normal"], np.float64)
                        offset = float(addition["offset_mm"])
                        if normal.shape != (3,) or not np.isfinite(normal).all() or not np.isfinite(offset) or not np.any(normal):
                            raise ValueError("新增支撑方向或偏置无效")
                        # 独立有理数核对工具的所有顶点，不能信任运行记录中的通过布尔值。
                        exact_n = [Fraction(float(x)) for x in normal]
                        contains = all(sum(a * Fraction(float(x)) for a, x in zip(exact_n, point)) <= Fraction(offset)
                                       for point in tool.vertices)
                        added_plane_containment_passed = added_plane_containment_passed and contains
                        if addition["plane_id"] != len(n):
                            raise ValueError("新增支撑编号与实际拼接顺序不符")
                        n, b = np.vstack([n, normal]), np.append(b, offset)
                    expanded.append((n, b))
                planes = expanded
'''
    text = text.replace(marker, extra + marker)
    text = text.replace('entry["passed"] = bool(valid and parent_matches and identity_passed', 'entry["added_plane_containment_passed"] = added_plane_containment_passed\n            entry["passed"] = bool(valid and parent_matches and identity_passed and added_plane_containment_passed')
    (qa / "audit_completed_support_outputs.py").write_text(text, "utf8")
    write_manifest(qa)
    print(output, flush=True)
    print(qa, flush=True)


if __name__ == "__main__":
    main()
