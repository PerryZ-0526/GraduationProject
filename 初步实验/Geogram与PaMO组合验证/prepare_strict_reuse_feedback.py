"""从最低R256冻结版本仅新增严格无变化复用入口，保留旧版本不改写。"""

import hashlib
import json
from pathlib import Path
import shutil


def main():
    here = Path(__file__).resolve().parent
    original = here / "run_minimum_resolution_feedback.py"
    text = original.read_text("utf8")
    text = text.replace('import trimesh\n', 'import trimesh\nfrom strict_no_change_reuse import try_strict_no_change_reuse\nfrom exact_oriented_surface_identity import exact_oriented_surface_identity\n', 1)
    start = text.index('            print(event, "GPU_and_correction_started"')
    end = text.index('            row["attempt"] = attempt', start)
    gpu = text[start:end]
    # 有变化的事件仍执行原完整GPU路径，无变化复用拒绝后直接保留拒绝证据。
    reuse = '''            raw_source = trimesh.load(folder / "source.obj", force="mesh", process=False)
            raw_bits = json.loads((folder / "labels.json").read_text("utf8"))["operand_bits"]
            row["raw_boolean_identity"] = exact_oriented_surface_identity(
                trimesh.load(parent, force="mesh", process=False), raw_source, raw_bits)
            prefix = set(route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index(event) + 1])
            cumulative_tools = [args.prepared / "inputs" / t["mesh"] for t in route["prefix_tools"] if t["event_id"] in prefix]
            # 原始布尔输出和准备后源均严格相同才允许复用，不能由清理掩盖变化。
            attempt = try_strict_no_change_reuse(engine, parent, source_path, labels_path,
                cumulative_tools, destination) if row["raw_boolean_identity"]["same"] else None
            if attempt is not None:
                row["execution_role"] = "strict_no_change_reuse"
                print(event, attempt["status"], flush=True)
            else:
                row["execution_role"] = "full_GPU_and_correction"
'''
    text = text[:start] + reuse + ''.join('    ' + line if line.strip() else line for line in gpu.splitlines(keepends=True)) + text[end:]
    text = text.replace('"GPU_calls_per_event": 1', '"GPU_calls_per_changed_event": 1, "strict_no_change_GPU_calls": 0')
    text = text.replace('"events": len(route["cutting_prefix_ids"]),', '"full_GPU_calls": sum(r.get("execution_role") == "full_GPU_and_correction" for r in report["rows"]),\n                     "strict_reuses": sum(r.get("execution_role") == "strict_no_change_reuse" and r["status"] == "published_geometry_observation" for r in report["rows"]),\n                     "events": len(route["cutting_prefix_ids"]),')
    entry = here / "run_strict_reuse_feedback.py"
    entry.write_text(text, "utf8")
    old = here.parent / "Geogram与PaMO切削排斥冻结_20261005_统一最低分辨率256薄壁三刀反馈"
    frozen = here.parent / "Geogram与PaMO切削排斥冻结_20261005_严格无变化复用薄壁三刀反馈"
    frozen.mkdir(exist_ok=False)
    rows = json.loads((old / "01-执行源码冻结清单.json").read_text("utf8"))
    for row in rows:
        source = old / row["file"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("原冻结源码摘要改变")
        shutil.copyfile(source, frozen / row["file"])
    for name in (entry.name, "strict_no_change_reuse.py", "exact_oriented_surface_identity.py"):
        shutil.copyfile(here / name, frozen / name)
        rows.append({"file": name, "sha256": hashlib.sha256((frozen / name).read_bytes()).hexdigest()})
    (frozen / "01-执行源码冻结清单.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf8")
    print(frozen, flush=True)


if __name__ == "__main__":
    main()
