"""结算补充支撑版本七家族，不混入下一原始目标提案版本。"""

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
    control_root = root / "20261005_补充面法向倍率4六家族18事件完整开发"
    control_path = control_root / "01-六家族完整执行与独立复审记录.json"
    assert json.loads(control_path.read_text("utf8"))["status"] == "completed_with_recorded_outcomes"
    prepared = root / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
    routes = json.loads((prepared / "01-完整范围冻结清单.json").read_text("utf8"))["routes"]
    snapshot = here.parent / "Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈"
    numerical = snapshot / "01-执行源码冻结清单.json"
    for item in json.loads(numerical.read_text("utf8")):
        assert sha(snapshot / item["file"]) == item["sha256"]
    rows = []
    for route in routes:
        rid = route["id"]
        thin = rid.startswith("薄壁_")
        batch = root / "20261005_补充面法向倍率4薄壁三刀真实反馈" if thin else control_root / rid
        qa = root / "20261005_补充支撑倍率4薄壁保存独立复审" if thin else control_root / (rid + "_保存复审")
        bp, qp = batch / "01-统一配置完整父反馈记录.json", qa / "01-保存候选整面与材料侧独立复审.json"
        b, q = json.loads(bp.read_text("utf8")), json.loads(qp.read_text("utf8"))
        assert b["status"] == "completed_with_recorded_outcomes" and q["status"] == "completed"
        assert b["snapshot_sha256"] == sha(numerical) and q["source_batch_sha256"] == sha(bp)
        assert [r["event"] for r in b["rows"]] == route["cutting_prefix_ids"]
        assert b["summary"]["published"] == q["summary"]["saved_candidates"] == q["summary"]["passed"]
        rows.append({"route": rid, "summary": b["summary"], "saved_passed": q["summary"]["passed"],
                     "batch_sha256": sha(bp), "qa_sha256": sha(qp), "outcomes": [r["status"] for r in b["rows"]]})
    summary = {"events": 21, "routes": 7, "published": sum(r["summary"]["published"] for r in rows),
        "complete_routes": sum(r["summary"]["whole_route_complete"] for r in rows),
        "saved_passed": sum(r["saved_passed"] for r in rows), "GPU_attempts": sum(r["summary"]["full_GPU_calls"] for r in rows),
        "strict_reuses": sum(r["summary"]["strict_reuses"] for r in rows), "status_counts": dict(Counter(s for r in rows for s in r["outcomes"]))}
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日%H时%M分%S秒")
    output = root / "20261005_补充支撑倍率4七家族同版终态核对"
    output.mkdir(exist_ok=False)
    record = output / "01-同版七家族终态与保存核对.json"
    record.write_text(json.dumps({"生成时间": now, "修改时间及修改内容": "首次生成，同版完整分母",
        "文档概述": "不混入下一原始顶点提案静态成功或运行中的新父反馈", "索引目录": ["rows", "summary"],
        "status": "completed", "snapshot_manifest_sha256": sha(numerical), "rows": rows, "summary": summary}, ensure_ascii=False, indent=2), "utf8")
    bindings = [root / "20261005_旧倍率4第二刀同文件支撑补充因果复审/01-同文件新旧支撑方法因果对照.json",
        root / "20261005_补充支撑独立复审伪造偏置负例/01-伪造通过标记与偏置独立复审负例.json",
        root / "20261005_薄壁第三刀原始顶点目标局部投影同源对照/02-原始目标与参照种子同GPU对照核查.json",
        root / "20261005_薄壁第三刀两点修正保存独立复审/01-两点修正保存网格完整独立复审.json"]
    assets = root / "可复用磨削测试集"
    versions = [int(m.group(1)) for p in assets.iterdir() if (m := re.search(r"_v(\d+)$", p.name))]
    asset = assets / f"补充支撑正负例与两点修正同源回归_v{max(versions, default=0) + 1}"
    asset.mkdir(exist_ok=False)
    mapping = [(path, f"{i + 1:02d}-{path.name.split('-', 1)[1]}") for i, path in enumerate(bindings)]
    mapping += [(root / "20261005_倍率4薄壁三刀真实父反馈/薄壁_新参数1p4375_交叉_e0_candidate_boolean/candidate.obj", "05-旧拒绝事件父网格.obj"),
        (root / "20261005_补充面法向倍率4薄壁三刀真实反馈/薄壁_新参数1p4375_交叉_e2_candidate_boolean/raw_full_candidate.obj", "06-第三刀原始GPU网格.obj"),
        (root / "20261005_薄壁第三刀原始顶点目标局部投影同源对照/01-原始目标投影候选.obj", "07-第三刀仅两点修正网格.obj")]
    for path, name in mapping:
        shutil.copyfile(path, asset / name)
    (asset / "08-同源正负例资产绑定清单.json").write_text(json.dumps({"生成时间": now, "修改时间及修改内容": "首次生成，分别绑定静态因果与连续版本",
        "文档概述": "静态两点成功不改连续2/3；伪造证据必须拒绝", "索引目录": ["files"],
        "files": [{"file": name, "sha256": sha(asset / name), "origin": str(path)} for path, name in mapping]}, ensure_ascii=False, indent=2), "utf8")
    number = max(int(m.group(1)) for p in here.glob("*.md") if (m := re.match(r"(\d+)-", p.name))) + 1
    doc = here / f"{number:02d}-补充支撑同版七家族终态与两点局部修正因果对照.md"
    table = "\n".join(f"| {r['route']} | {r['summary']['published']}/3 | {r['saved_passed']} | {', '.join(s for s in r['outcomes'] if s != 'published_geometry_observation')} |" for r in rows)
    content = f'''# 补充支撑同版七家族终态与两点局部修正因果对照

> 生成时间：{now}（北京时间）
> 修改时间及修改内容：{now}，首次生成；仅结算补充支撑倍率4版本，不改124号旧终态。
> 文档概述：同版{summary['published']}/21发布、{summary['complete_routes']}/7完整，保存{summary['saved_passed']}/{summary['published']}通过；薄壁2/3，第三刀静态原始顶点目标只动2点通过并独立复审，新的真实反馈35069正在运行。
> 索引目录：[终态](#终态) · [支撑因果与负例](#支撑因果与负例) · [第三刀目标对照](#第三刀目标对照) · [证据与后续](#证据与后续)

## 终态

| 已见开发路线 | 发布 | 保存复审 | 其他结果 |
|---|---|---|---|
{table}

GPU进程启动{summary['GPU_attempts']}次，严格复用{summary['strict_reuses']}次；本批均在终态，不称未见评价或整体交付。板体3/3改善与倍率4整体配置有关，未触发复用补支撑，不能将其成功归因于面法向补充。

## 支撑因果与负例

补充拒绝面的正负法向作为工具支撑方向。偏置必须外舍入包住全部工具顶点，再以有理数精确核对工具包含性与三角面三顶点；物理顶点不动，完整嵌入和工具内部材料外锚点门槛保持。

124号旧第二刀完全相同的父、布尔源、标签和两工具文件，旧方法拒绝；新方向同文件静态获证，输出文件SHA与旧父完全相同，0次新GPU、0次发布。该直接对照避免把新首刀GPU的微小变化冒充支撑因果。

4项单元测试通过：真实拒绝面不动顶点获证、伪造偏置拒绝、真实交叉面拒绝、35拒绝面不受失败摘要20条上限截断。复制证据伪造偏置并保留通过标记的独立复审负例通过：表面支撑仍通过，但重新算工具包含性失败，整事件拒绝。原实验文件未改写。

## 第三刀目标对照

薄壁第三刀实际改变几何，完整GPU及工作源门控通过，原始网格闭合嵌入合法；原参照种子提案没有合法输出，连续仍计2/3。原始GPU的两张面对三个工具未获原方向、自身法向或边叉积方向证明，不能将此失败当作精确相交证书。

同一个已保存GPU对象，以原始顶点为优化目标而不先做全网格最近点恢复，沿既有0.1毫米原始位移信赖域做一次局部排斥提案，只移动2点，最大位移约0.012262879毫米；所有整面及材料侧证明、完整嵌入通过。重新加载保存候选，原冻结面支撑和3个新锚点独立复审通过，面连接完全相同。该0.1毫米为算法修正预算，不是输出几何最大误差门槛。

静态修正网格体积约9.393586 mm³，双向面积样本0.1毫米内最低占比约99.865723%，低于10度面比例约0.086157%。统计不用于固定几何达标判定，也不认证修正移动路径CCD。静态成功不改旧拒绝，新增原始目标提案版本已冻结，从初态三刀35069实际运行，尚未结算。

## 证据与后续

同版终态：`{record}`，SHA`{sha(record)}`；数值清单SHA`{sha(numerical)}`。同文件因果、偏置负例、两点投影及独立保存复审的完整记录位于新资产`{asset}`，原始路径及逐文件SHA保存。

六家族3910与薄壁84809终态；GPU保持开启。下一版只增加一次原始顶点提案，触发条件为原预算无合法候选，不重复GPU、不省略原合法性审查。完成新三刀后必须独立保存复审，再扩大同版本范围。倍率4也会使有几何变化的反馈事件面数快速增长，仍是诊断配置，后续须研究特征保护及有界预算，不能将固定倍率称创新或最终算法。长序列、未见、小特征和在线交付均未完成，目标继续推进。
'''
    with doc.open("x", encoding="utf8") as stream:
        stream.write(content)
    plan = project / "课题规划与专题调研/40-累计切削域排斥连续验证推进记录.md"
    lines = plan.read_text("utf8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("> **修改时间及修改内容**"):
            lines[i] = f"> **修改时间及修改内容**：{now}，补充{number}号补充支撑同版七家族终态与两点原始目标修正。"
        if line.startswith("> **文档概述**"):
            lines[i] = f"> **文档概述**：补充支撑倍率4同版{summary['published']}/21发布、{summary['complete_routes']}/7完整，全部保存复审；薄壁2/3，第三刀两点静态修正及独立复审通过，原始目标新反馈35069运行，目标未完成。"
    plan.write_text("\n".join(lines) + f"\n修改时间及修改内容：{now}，补充支撑同版{summary['published']}/21及全部保存复审通过。旧同文件第二刀因果静态证明通过；第三刀原始目标两点修正通过并独立复审，不改原2/3。新三刀35069运行，见组合验证{number}号，目标未完成。\n", "utf8")
    print(summary, flush=True)
    print(doc, flush=True)


if __name__ == "__main__":
    main()
