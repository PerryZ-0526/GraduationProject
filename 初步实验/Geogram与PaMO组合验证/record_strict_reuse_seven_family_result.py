"""核对同版七家族完整分母，区分启动GPU、实际完整求解和严格复用。"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil
from collections import Counter


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    project = Path.cwd()
    here = project / "初步实验/Geogram与PaMO组合验证"
    root = Path("D:/GraduationProject_切削排斥证据")
    control_root = root / "20261005_严格复用同版六家族18事件完整开发"
    control_path = control_root / "01-六家族完整执行与独立复审记录.json"
    control = json.loads(control_path.read_text("utf8"))
    if control["status"] != "completed_with_recorded_outcomes":
        raise ValueError("原控制进程尚未终态，禁止提前结算")
    prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
    manifest = prepared / "01-完整范围冻结清单.json"
    routes = json.loads(manifest.read_text("utf8"))["routes"]
    snapshot = here.parent / "Geogram与PaMO切削排斥冻结_20261005_严格无变化复用薄壁三刀反馈"
    numerical_manifest = snapshot / "01-执行源码冻结清单.json"
    for item in json.loads(numerical_manifest.read_text("utf8")):
        assert sha(snapshot / item["file"]) == item["sha256"]
    rows = []
    for route in routes:
        rid = route["id"]
        thin = rid.startswith("薄壁_")
        batch = root / "20261005_严格无变化复用薄壁三刀真实反馈" if thin else control_root / rid
        qa = root / "20261005_严格复用薄壁三保存独立复审" if thin else control_root / (rid + "_保存复审")
        bp = batch / "01-统一配置完整父反馈记录.json"
        qp = qa / "01-保存候选整面与材料侧独立复审.json"
        b, q = json.loads(bp.read_text("utf8")), json.loads(qp.read_text("utf8"))
        assert b["status"] == "completed_with_recorded_outcomes" and q["status"] == "completed"
        assert b["snapshot_sha256"] == sha(numerical_manifest) and b["manifest_sha256"] == sha(manifest)
        assert q["source_batch_sha256"] == sha(bp)
        assert [r["event"] for r in b["rows"]] == route["cutting_prefix_ids"]
        published = [r for r in b["rows"] if r["status"] == "published_geometry_observation"]
        assert len(published) == q["summary"]["saved_candidates"] == q["summary"]["passed"]
        for item in published:
            assert sha(batch / f"{rid}_{item['event']}_candidate_boolean/candidate.obj") == item["output_sha256"]
        rows.append({"route": rid, "batch_sha256": sha(bp), "qa_sha256": sha(qp),
                     "summary": b["summary"], "saved_passed": q["summary"]["passed"],
                     "outcomes": [{"event": r["event"], "status": r["status"],
                         "execution_role": r.get("execution_role"),
                         "GPU_returncode": r.get("attempt", {}).get("execution", {}).get("returncode"),
                         "working_gate": r.get("actual_working_source_gate", {}).get("status"),
                         "attempt_status": r.get("attempt", {}).get("status"),
                         "minimum_area_fraction_within_0_1_mm": r.get("cumulative_distribution", {}).get("minimum_bidirectional_area_fraction_within_0_1_mm")}
                         for r in b["rows"]]})
    outcomes = [o for row in rows for o in row["outcomes"]]
    summary = {"events": len(outcomes), "routes": len(rows),
               "published": sum(r["summary"]["published"] for r in rows),
               "complete_routes": sum(r["summary"]["whole_route_complete"] for r in rows),
               "saved_passed": sum(r["saved_passed"] for r in rows),
               "GPU_process_attempts": sum(o["execution_role"] == "full_GPU_and_correction" for o in outcomes),
               "full_solver_completed": sum(o["execution_role"] == "full_GPU_and_correction" and o["GPU_returncode"] == 0 and o["working_gate"] == "passed_before_full_solver" for o in outcomes),
               "strict_reuses": sum(o["execution_role"] == "strict_no_change_reuse" and o["status"] == "published_geometry_observation" for o in outcomes),
               "status_counts": dict(Counter(o["status"] for o in outcomes))}
    assert summary["events"] == 21 and summary["routes"] == 7
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日%H时%M分%S秒")
    output = root / "20261005_严格复用七家族同版终态核对"
    output.mkdir(exist_ok=False)
    record = output / "01-七家族同数值版本完整核对.json"
    record.write_text(json.dumps({"生成时间": now, "修改时间及修改内容": "首次生成，同一数值清单与完整分母核对",
        "文档概述": "合并同版薄壁及六其他家族，不混入旧版本成功事件", "索引目录": ["rows", "summary"],
        "status": "completed", "snapshot_manifest_sha256": sha(numerical_manifest),
        "input_manifest_sha256": sha(manifest), "controller_sha256": sha(control_path), "rows": rows,
        "summary": summary, "continuous_geometry_certified": False}, ensure_ascii=False, indent=2), "utf8")
    negative = root / "20261005_严格复用包围凸工具盒体负例"
    negative_record = negative / "02-材料侧必需性负例核查.json"
    assert json.loads(negative_record.read_text("utf8"))["summary"]["passed"]
    assets = root / "可复用磨削测试集"
    versions = [int(m.group(1)) for p in assets.iterdir() if (m := re.search(r"_v(\d+)$", p.name))]
    asset = assets / f"整面支撑通过但工具被材料包围负例_v{max(versions, default=0) + 1}"
    asset.mkdir(exist_ok=False)
    mapping = [(negative / "parent.obj", "01-盒体父与无变化源.obj"), (negative / "labels.json", "02-父来源标签.json"),
               (negative / "01-材料内部人工凸工具.obj", "03-内部凸工具.obj"), (negative_record, "04-精确材料侧拒绝证明.json")]
    for source, name in mapping:
        shutil.copyfile(source, asset / name)
    (asset / "05-负例资产绑定清单.json").write_text(json.dumps({"生成时间": now, "修改时间及修改内容": "首次生成，认证器人工负例",
        "文档概述": "不能凭表面排斥判工具在材料外；不冒充实际布尔事件", "索引目录": ["files"],
        "files": [{"file": name, "sha256": sha(asset / name)} for _, name in mapping]}, ensure_ascii=False, indent=2), "utf8")
    number = max(int(m.group(1)) for p in here.glob("*.md") if (m := re.match(r"(\d+)-", p.name))) + 1
    doc = here / f"{number:02d}-严格复用七家族同版终态与编码自交负例.md"
    table = "\n".join(f"| {r['route']} | {r['summary']['published']}/3 | {r['saved_passed']} | " + ", ".join(o['status'] for o in r['outcomes'] if o['status'] != 'published_geometry_observation') + " |" for r in rows)
    content = f'''# 严格复用七家族同版终态与编码自交负例

> 生成时间：{now}（北京时间）
> 修改时间及修改内容：{now}，首次生成；记录七家族完整同版本终态，不改旧批次。
> 文档概述：同版本{summary['published']}/21观察发布、{summary['complete_routes']}/7完整，保存{summary['saved_passed']}/{summary['published']}复审通过。薄壁严格复用成功，板体实际编码自交拒绝，首刀形状与小特征缺口仍待解决。
> 索引目录：[终态](#终态) · [负例](#负例) · [证据与下一步](#证据与下一步)

## 终态

| 开发路线 | 发布 | 保存复审通过 | 其余状态 |
|---|---|---|---|
{table}

GPU进程启动{summary['GPU_process_attempts']}次，其中实际工作源门控通过且完整三阶段返回0共{summary['full_solver_completed']}次；严格无变化复用{summary['strict_reuses']}次。门控拒绝不算完整求解成功。所有已发布对象重新绑定原输入清单、同一数值快照清单、实际父链、源/标签、累计工具与独立参照，并保存复审。

本批全为已见开发输入，不能称未见评价；完整路线只表示规定事件都有合法观察输出。误差只按分布报告，不设固定最大值或达标率。薄壁三事件双向面积0.1毫米内约97.5%至97.8%，约0.83毫米尾部和首刀体积损失仍存在，不能从复用成功推出特征保持。

## 负例

板体第二刀物理FP64源通过，但实际GPU初始编码源有5对精确自交，完整求解前门控拒绝，第三刀阻断。该新父链由最低R256等完整版本生成，当前不能从跨版本成绩单独归因于分辨率。精确面号定位得到519/521、552/520、574/520、552/521、574/521五对（从0编号）；519翻转，其余涉及的面法向仍为正，四对跨父来源1与工具来源2。正法向不足以排除编码交叠。只读证据位于`D:/GraduationProject_切削排斥证据/20261005_严格复用同版板体第二刀编码交叠定位/01-板体物理合法但编码交叠逐面诊断.json`；首次在NumPy整数JSON序列化处退出1，转换原生整数后同输入只读重查保存，未重跑GPU。椭球及弯曲骨样体第三刀独立参照拒绝保留，不能用失败参照继续评价。

人工盒体包围内部凸工具的认证器负例通过：相同有向表面、闭合嵌入和全部整面支撑通过，但精确材料侧锚点均处于材料内部，因此复用拒绝。该负例不冒充真实Geogram布尔输出。前两次试构造薄壁内部工具也被正确拒绝，但整面支撑同时失败，未成功隔离材料侧条件；其原始记录保留，不计入这个条件的通过数。新资产位于`{asset}`。

## 证据与下一步

同版核对：`{record}`，SHA`{sha(record)}`；数值快照`{snapshot}`，清单SHA`{sha(numerical_manifest)}`。主控制进程65142已终态；不关闭用户GPU，不改另一分支作者安装。

下一步从本次板体保存物理源及实际编码源定位5对交叠，验证能保持来源及几何的局部修复；同时继续薄壁阶段二/三边角损失定位。首刀几何保持、小特征、长序列、未见评价、连续几何和在线交付仍未完成，研究目标保持推进。
'''
    with doc.open("x", encoding="utf8") as stream:
        stream.write(content)
    plan = project / "课题规划与专题调研/40-累计切削域排斥连续验证推进记录.md"
    lines = plan.read_text("utf8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("> **修改时间及修改内容**"):
            lines[index] = f"> **修改时间及修改内容**：{now}，补充{number}号同版七家族完整终态及材料侧负例。"
        if line.startswith("> **文档概述**"):
            lines[index] = f"> **文档概述**：严格复用同版{summary['published']}/21发布、{summary['complete_routes']}/7完整，{summary['saved_passed']}/{summary['published']}保存复审；板体第二刀实际编码5对自交拒绝，薄壁首刀形状缺口仍存在。下一步编码交叠修复与薄壁边缘保持，目标未完成。"
    plan.write_text("\n".join(lines) + f"\n修改时间及修改内容：{now}，同版七家族核对{summary['published']}/21发布、{summary['complete_routes']}/7完整，全部发布保存复审通过。GPU启动{summary['GPU_process_attempts']}、完整求解返回0共{summary['full_solver_completed']}、严格复用{summary['strict_reuses']}。板体新编码自交负例与材料侧必要性负例保留，见组合验证{number}号。控制65142退出，实例保持开启，研究目标未完成。\n", "utf8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    print(doc, flush=True)


if __name__ == "__main__":
    main()
