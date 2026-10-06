"""基于补充面法向版本增加一个原始顶点局部投影提案，旧版本保持不变。"""

import hashlib
import json
from pathlib import Path
import shutil


def manifest(folder):
    rows = [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir()) if p.is_file() and p.name != "01-执行源码冻结清单.json"]
    (folder / "01-执行源码冻结清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf8")


def main():
    here = Path(__file__).resolve().parent
    old = here.parent / "Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈"
    output = here.parent / "Geogram与PaMO切削排斥冻结_20261005_原始顶点局部提案薄壁反馈"
    output.mkdir(exist_ok=False)
    for row in json.loads((old / "01-执行源码冻结清单.json").read_text("utf8")):
        assert hashlib.sha256((old / row["file"]).read_bytes()).hexdigest() == row["sha256"]
        shutil.copyfile(old / row["file"], output / row["file"])
    shutil.copyfile(here / "raw_seed_after_reference_failure.py", output / "raw_seed_after_reference_failure.py")
    text = (old / "run_completed_support_feedback.py").read_text("utf8")
    text = text.replace('observation.distribution_ranked_exclusion = quality_ranked_exclusion', 'from raw_seed_after_reference_failure import raw_seed_after_reference_failure\nobservation.distribution_ranked_exclusion = raw_seed_after_reference_failure')
    text = text.replace('simplification_target_ratio=4,', 'simplification_target_ratio=4, raw_seed_extra_proposals_budget=1, postprocessing_trigger="no_legal_candidate_in_original_fixed_budget",')
    text = text.replace('"fallback": "none"', '"fallback": "no_original_method_fallback"')
    (output / "run_raw_seed_feedback.py").write_text(text, "utf8")
    manifest(output)
    oldqa = here.parent / "Geogram与PaMO切削排斥冻结_20261005_补充支撑独立保存复审"
    qa = here.parent / "Geogram与PaMO切削排斥冻结_20261005_原始顶点提案独立保存复审"
    qa.mkdir(exist_ok=False)
    shutil.copyfile(oldqa / "exact_oriented_surface_identity.py", qa / "exact_oriented_surface_identity.py")
    text = (oldqa / "audit_completed_support_outputs.py").read_text("utf8")
    marker = '                    details = dict(outer["proposal_generator"], selected_level=outer["selected_original_attempt_index"],'
    start = text.index(marker)
    end = text.index('                path = args.batch', start)
    original = text[start:end]
    text = text[:start] + '''                    raw_seed = outer.get("proposal_role") == "raw_seed_projection_after_failed_reference_proposals"
                    if raw_seed:
                        details = dict(outer, cumulative_tool_sha256=outer["cumulative_tool_sha256"],
                            cumulative_reference_sha256=outer["cumulative_reference_sha256"])
                    else:
''' + ''.join('    ' + line for line in original.splitlines(keepends=True)) + text[end:]
    text = text.replace('            else:\n                selections = details["attempts"]', '            elif raw_seed:\n                selections = details["raw_seed_projection"]["frozen_face_support_ids"]\n            else:\n                selections = details["attempts"]')
    (qa / "audit_raw_seed_outputs.py").write_text(text, "utf8")
    manifest(qa)
    print(output, flush=True)
    print(qa, flush=True)


if __name__ == "__main__":
    main()
