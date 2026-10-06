"""伪造新增支撑偏置但保留通过标记，独立保存复审必须重新计算并拒绝。"""

import json
from pathlib import Path
import shutil
import subprocess
import sys

from run_constrained_batch import RemoteQuality
from run_geometry_study import save, now
from audit_followup_candidate import sha256


def main():
    project = Path.cwd()
    root = Path("D:/GraduationProject_切削排斥证据")
    original = root / "20261005_补充面法向倍率4薄壁三刀真实反馈"
    original_record = original / "01-统一配置完整父反馈记录.json"
    original_hash = sha256(original_record)
    report = json.loads(original_record.read_text("utf8"))
    assert report["status"] == "completed_with_recorded_outcomes"
    output = root / "20261005_补充支撑独立复审伪造偏置负例"
    output.mkdir(exist_ok=False)
    batch = output / "tampered_batch"
    shutil.copytree(original, batch)
    row = report["rows"][1]
    additions = [addition for certificate in row["attempt"]["cumulative_tools"] for addition in certificate["support_completion"]["added_planes"]]
    assert additions
    # 坐标、面与摘要不改；只压低偏置，故表面支撑可能仍通过，但工具包含性必需重算。
    old_offset = additions[0]["offset_mm"]
    additions[0]["offset_mm"] -= 1e-6
    save(batch / "01-统一配置完整父反馈记录.json", report)
    qa = project / "初步实验/Geogram与PaMO切削排斥冻结_20261005_补充支撑独立保存复审"
    launcher = project / "初步实验/Geogram与PaMO切削排斥冻结_20261005_补充支撑倍率4六家族执行控制/frozen_feedback_child.py"
    args = [sys.executable, "-X", "utf8", str(launcher), str(qa), str(qa / "audit_completed_support_outputs.py"),
        "--prepared", str(root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"), "--batch", str(batch),
        "--source-batch", str(batch), "--side-validation", str(project / "初步实验/Geogram与PaMO组合验证/实验结果/20261004_切削排斥精确材料侧分类开发"),
        "--output", str(output / "saved_audit"), "--kind", "unified"]
    execution = subprocess.run(args, capture_output=True, text=True, encoding="utf8", errors="replace")
    (output / "stdout.log").write_text(execution.stdout, "utf8")
    (output / "stderr.log").write_text(execution.stderr, "utf8")
    assert execution.returncode == 0
    qp = output / "saved_audit/01-保存候选整面与材料侧独立复审.json"
    q = json.loads(qp.read_text("utf8"))
    audited = next(r for r in q["rows"] if r["event"] == "e1")
    assert not audited["added_plane_containment_passed"] and not audited["passed"]
    assert all(c["passed"] for c in audited["face_certificates"])
    assert sha256(original_record) == original_hash
    save(output / "01-伪造通过标记与偏置独立复审负例.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，复制证据中故意扰动认证偏置",
        "文档概述": "表面支撑通过仍需完整工具包含性；原实验未改写", "索引目录": ["summary"],
        "summary": {"passed": True, "event": "e1", "face_support_passed": True, "added_tool_containment_passed": False},
        "original_record_sha256": original_hash, "tampered_record_sha256": sha256(batch / "01-统一配置完整父反馈记录.json"),
        "saved_audit_sha256": sha256(qp), "old_offset": old_offset, "tampered_offset": additions[0]["offset_mm"],
        "new_GPU_calls": 0})
    print("independent_tampered_offset_rejected", flush=True)


if __name__ == "__main__":
    main()
