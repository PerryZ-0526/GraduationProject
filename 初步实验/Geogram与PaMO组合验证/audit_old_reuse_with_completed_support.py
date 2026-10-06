"""复用旧拒绝事件的完全相同文件，直接验证补支撑的因果作用，不新增GPU。"""

import getpass
import json
import os
from pathlib import Path
import sys


def main():
    project = Path.cwd()
    snapshot = project / "初步实验/Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈"
    sys.path.insert(0, str(snapshot))
    from run_constrained_batch import RemoteQuality
    from run_geometry_study import execute, save, now
    from cut_side_classifier import ExactCutSide
    from audit_followup_candidate import sha256
    from strict_no_change_reuse import try_strict_no_change_reuse
    root = Path("D:/GraduationProject_切削排斥证据")
    batch = root / "20261005_倍率4薄壁三刀真实父反馈"
    bp = batch / "01-统一配置完整父反馈记录.json"
    b = json.loads(bp.read_text("utf8"))
    row = b["rows"][1]
    assert row["attempt"]["status"] == "strict_reuse_legality_rejected"
    parent = batch / "薄壁_新参数1p4375_交叉_e0_candidate_boolean/candidate.obj"
    source = batch / "薄壁_新参数1p4375_交叉_e1_candidate_input/clean_source.obj"
    labels = source.with_name("clean_labels.json")
    assert sha256(parent) == row["parent_sha256"]
    prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
    route = next(r for r in json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"] if r["id"] == row["route"])
    prefix = route["cutting_prefix_ids"][:2]
    tools = [prepared / "inputs" / t["mesh"] for t in route["prefix_tools"] if t["event_id"] in prefix]
    assert [sha256(p) for p in tools] == [x["tool_sha256"] for x in row["attempt"]["cumulative_tools"]]
    output = root / "20261005_旧倍率4第二刀同文件支撑补充因果复审"
    output.mkdir(exist_ok=False)
    cfg = dict(line.split("=", 1) for line in (project / ".env").read_text("utf8").splitlines() if line and not line.startswith("#"))
    getpass.getpass = lambda _: cfg["CUDA_SSH_PASSWORD"]
    os.environ["GPU_SSH_HOST"] = "connect.westb.seetacloud.com"
    engine = RemoteQuality(output, 51667)
    try:
        assert execute(engine.client, ["mkdir", engine.remote])["returncode"] == 0
        validation = json.loads((project / "初步实验/Geogram与PaMO组合验证/实验结果/20261004_切削排斥精确材料侧分类开发/01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))["environment"]
        assert execute(engine.client, ["sha256sum", validation["executable"]])["stdout"].split()[0] == validation["executable_sha256"]
        engine.side = ExactCutSide(engine, validation["executable"])
        result = try_strict_no_change_reuse(engine, parent, source, labels, tools, output / "same_parent_candidate")
        assert result["status"] == "accepted_geometry_observation"
        assert result["output_sha256"] == sha256(parent)
        save(output / "01-同文件新旧支撑方法因果对照.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，旧拒绝事件不换输入复审",
            "文档概述": "输入、源、标签、工具、父与输出坐标完全相同，仅补支撑方向；不改旧终态",
            "索引目录": ["result"], "original_batch_sha256": sha256(bp),
            "old_status": row["attempt"]["status"], "new_status": result["status"], "result": result,
            "new_GPU_calls": 0, "new_publications": 0})
        print("same_files_completed_support_passed", flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
