"""复用原保存复审并核对新增固定锚点，支持已完成子路线和整批终态。"""
from pathlib import Path
import sys
import recheck_shared_feedback as shared
from preserved_controller_source import replace_once


def build_anchor_recheck(source):
    source = "from audit_published_anchor_records import check_anchor_record\n"+source
    source = replace_once(source, "                fixed_ok = True\n", "                fixed_ok = True\n                anchor_ok = True\n")
    marker = "                    fixed_ok = fixed_ok and np.array_equal(mesh.faces, before.faces)\n"
    inserted = """                    # 原顶点和新增固定点都必须在实际保存网格中保持投影前位置。
                    anchors = attempt.get("anchor_updates")
                    if anchors is None:
                        anchor_ok = attempt.get("projection") == "no_free_vertices_identity"
                    else:
                        actual_anchors = json.loads((folder/"anchor_updates.json").read_text(encoding="utf-8"))
                        anchor_ok = actual_anchors == anchors and check_anchor_record(anchors, ids)
                        for update in anchors["updates"]:
                            added = update["added_vertices"]
                            anchor_ok = anchor_ok and np.array_equal(mesh.vertices[added], before.vertices[added])
"""
    source = replace_once(source, marker, marker+inserted)
    # 原顶点与新增锚点分开报告；接受条件同时要求两者，便于定位各自的失败。
    source = replace_once(source, "passed = passed and geometry[\"probe_max_mm\"] <= .1",
        "passed = passed and anchor_ok and geometry[\"probe_max_mm\"] <= .1")
    return replace_once(source, "fixed_original_vertices_exact=bool(fixed_ok), metrics=metrics,",
        "fixed_original_vertices_exact=bool(fixed_ok), fixed_added_anchors_exact=bool(anchor_ok), metrics=metrics,")


if __name__ == "__main__":
    # 原复审入口自行检查子路线完整或整批终态，不更改原执行记录的状态。
    combo = Path(__file__).resolve().parent
    output = Path(sys.argv[sys.argv.index("--output")+1])
    route = sys.argv[sys.argv.index("--route")+1] if "--route" in sys.argv else "full_batch"
    path = output/("anchored_saved_"+route+"_source.py")
    path.write_text(build_anchor_recheck(Path(shared.__file__).read_text(encoding="utf-8")), encoding="utf-8")
    shared.__file__ = str(path)
    entry = combo/("recheck_completed_preserved_route.py" if "--route" in sys.argv else "recheck_preserved_feedback.py")
    frozen = output/("anchored_saved_"+route+"_entry.py")
    frozen.write_bytes(entry.read_bytes())
    exec(compile(frozen.read_text(encoding="utf-8"), str(frozen), "exec"), dict(__name__="__main__", __file__=str(frozen)))
