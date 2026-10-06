"""原固定、新增锚点和初态编码锚点联合保存对象复审。"""
from pathlib import Path
import sys
import recheck_shared_feedback as shared
from recheck_anchored_saved import build_anchor_recheck
from preserved_controller_source import replace_once


def build_initial_recheck(source):
    source = build_anchor_recheck(source)
    source = 'from initial_encoding_saved_contract import check_initial_encoding_record\n'+source
    marker = '                    anchors = attempt.get("anchor_updates")\n'
    inserted = '''                    # 新规则必须绑定实际工作器详情并重算编码退化顶点，不能仅检查日志数量。
                    details = json.loads((folder/"details.json").read_text(encoding="utf-8"))
                    encoding_record = attempt.get("initial_encoding_anchors", {})
                    encoding_contract = check_initial_encoding_record(source.vertices, before.vertices,
                        before.faces, mesh.vertices, ids, encoding_record)
                    encoding_contract["details_match"] = details.get("initial_encoding_anchors") == encoding_record
                    anchor_ok = encoding_contract["passed"] and encoding_contract["details_match"]
'''
    source = replace_once(source, marker, inserted+marker)
    # 两类锚点均需成立，原追加锚点检查不能覆盖初态检查的结果。
    source = replace_once(source, 'anchor_ok = actual_anchors == anchors and check_anchor_record(anchors, ids)',
        'anchor_ok = anchor_ok and actual_anchors == anchors and check_anchor_record(anchors, ids)')
    source = replace_once(source, 'anchor_ok = attempt.get("projection") == "no_free_vertices_identity"',
        'anchor_ok = anchor_ok and attempt.get("projection") == "no_free_vertices_identity"')
    source = replace_once(source, 'fixed_added_anchors_exact=bool(anchor_ok), metrics=metrics,',
        'fixed_added_anchors_exact=bool(anchor_ok), initial_encoding_contract=encoding_contract if row["selected_method"] != "full" else None, metrics=metrics,')
    return source


if __name__ == '__main__':
    combo = Path(__file__).resolve().parent
    output = Path(sys.argv[sys.argv.index('--output')+1])
    route = sys.argv[sys.argv.index('--route')+1] if '--route' in sys.argv else 'full_batch'
    path = output/('initial_encoding_saved_'+route+'_source.py')
    path.write_text(build_initial_recheck(Path(shared.__file__).read_text(encoding='utf-8')), encoding='utf-8')
    shared.__file__ = str(path)
    entry = combo/('recheck_completed_preserved_route.py' if '--route' in sys.argv else 'recheck_preserved_feedback.py')
    frozen = output/('initial_encoding_saved_'+route+'_entry.py')
    frozen.write_bytes(entry.read_bytes())
    (output/'initial_encoding_saved_contract.py').write_bytes((combo/'initial_encoding_saved_contract.py').read_bytes())
    exec(compile(frozen.read_text(encoding='utf-8'), str(frozen), 'exec'), dict(__name__='__main__', __file__=str(frozen)))
