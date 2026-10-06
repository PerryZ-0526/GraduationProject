"""保存薄壁同输入简化预算因果诊断、完整父反馈终态及新的回归资产。"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    project = Path.cwd()
    here = project / "初步实验/Geogram与PaMO组合验证"
    root = Path("D:/GraduationProject_切削排斥证据")
    comparison_path = root / "20261005_薄壁同源三简化预算完整对照核对/01-三预算同源实际张量与各阶段统计.json"
    comparison = json.loads(comparison_path.read_text("utf8"))
    assert comparison["stage1_tensor_bitwise_identical"]
    batch = root / "20261005_倍率4薄壁三刀真实父反馈"
    bp = batch / "01-统一配置完整父反馈记录.json"
    b = json.loads(bp.read_text("utf8"))
    if b["status"] != "completed_with_recorded_outcomes":
        raise ValueError("父反馈实际进程未结束，不能结算")
    qp = root / "20261005_倍率4薄壁保存独立复审/01-保存候选整面与材料侧独立复审.json"
    q = json.loads(qp.read_text("utf8"))
    assert q["status"] == "completed" and q["source_batch_sha256"] == sha(bp)
    assert q["summary"]["saved_candidates"] == q["summary"]["passed"] == b["summary"]["published"]
    maintenance = []
    for ratio in (1, 2, 4):
        path = root / f"20261005_薄壁首刀预算{ratio}整面维护复审/01-首刀整面维护与保存复审.json"
        data = json.loads(path.read_text("utf8"))
        assert data["status"] == "completed" and data["maintenance"]["accepted"] and data["audit"]["passed"]
        maintenance.append({"ratio": ratio, "path": str(path), "sha256": sha(path), "audit": data["audit"]})
    source = root / "20261005_严格无变化复用薄壁三刀真实反馈/薄壁_新参数1p4375_交叉_e0_candidate_input/clean_source.obj"
    assets = root / "可复用磨削测试集"
    versions = [int(m.group(1)) for p in assets.iterdir() if (m := re.search(r"_v(\d+)$", p.name))]
    asset = assets / f"薄壁同简化输入三预算阶段回归_v{max(versions, default=0) + 1}"
    asset.mkdir(exist_ok=False)
    mapping = [(source, "01-同源物理网格.obj"), (comparison_path, "02-三预算实际输入与统计.json"),
               (root / "20261005_薄壁首刀同源简化预算对照_ratio1/stage_observations/stage1_centered.npz", "03-共同实际简化输入张量.npz")]
    for ratio in (1, 2, 4):
        folder = root / f"20261005_薄壁首刀同源简化预算对照_ratio{ratio}"
        mapping += [(folder / "stage_observations/stage2.obj", f"{len(mapping) + 1:02d}-倍率{ratio}简化输出.obj"),
                    (folder / "stage_observations/stage3.obj", f"{len(mapping) + 2:02d}-倍率{ratio}投影输出.obj")]
    for path, name in mapping:
        shutil.copyfile(path, asset / name)
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日%H时%M分%S秒")
    (asset / "10-同输入三预算资产绑定清单.json").write_text(json.dumps({"生成时间": now,
        "修改时间及修改内容": "首次生成，同源三预算阶段资产", "文档概述": "实际简化输入逐位同一，完整对照三组全部保留",
        "索引目录": ["files"], "files": [{"file": name, "sha256": sha(asset / name), "origin": str(path)} for path, name in mapping],
        "new_parent_feedback_summary": b["summary"], "batch_sha256": sha(bp), "saved_audit_sha256": sha(qp)}, ensure_ascii=False, indent=2), "utf8")
    number = max(int(m.group(1)) for p in here.glob("*.md") if (m := re.match(r"(\d+)-", p.name))) + 1
    doc = here / f"{number:02d}-薄壁简化损失同输入因果对照与倍率四真实反馈.md"
    raw_rows = [row for row in comparison["rows"] if row["stage"] == "stage3"]
    table = "\n".join(f"| {r['ratio']} | {r['faces']} | {r['volume_mm3']:.6f} | {r['geometry_distribution']['minimum_bidirectional_area_fraction_within_0_1_mm'] * 100:.6f}% | {r['geometry_distribution']['vertices_reverse']['max_mm']:.6f} | {r['quality']['angle_below_10_deg']['faces']}（{r['quality']['angle_below_10_deg']['fraction'] * 100:.6f}%） |" for r in raw_rows)
    maintained_table = "\n".join(f"| {r['ratio']} | {r['audit']['metrics']['volume_mm3']:.6f} | {r['audit']['cumulative_distribution']['minimum_bidirectional_area_fraction_within_0_1_mm'] * 100:.6f}% | {r['audit']['quality']['angle_below_10_deg']['faces']}（{r['audit']['quality']['angle_below_10_deg']['fraction'] * 100:.6f}%） | 通过 |" for r in maintenance)
    outcomes = "\n".join(f"- {row['event']}：{row['status']}，执行类型{row.get('execution_role', '未执行')}。" for row in b["rows"])
    content = f'''# 薄壁简化损失同输入因果对照与倍率四真实反馈

> 生成时间：{now}（北京时间）
> 修改时间及修改内容：{now}，首次生成；保存同输入三预算完整对照及新父反馈终态。
> 文档概述：同一次运行定位主要损失在简化阶段，三预算实际输入逐位相同；提高面预算改善形状但增加面数，新倍率4父反馈{b['summary']['published']}/3，保存复审{q['summary']['passed']}/{q['summary']['saved_candidates']}。
> 索引目录：[阶段归因](#阶段归因) · [同输入预算对照](#同输入预算对照) · [真实反馈](#真实反馈) · [证据与后续](#证据与后续)

## 阶段归因

源体积9.750477 mm³；同一次完整GPU运行，第一阶段211688面、体积9.822874 mm³；简化后634面、8.810050 mm³；投影后634面、8.751068 mm³。第一阶段反向顶点距离峰值约0.040189毫米，简化后约0.828760毫米，投影后约0.830091毫米。主要边角损失在简化阶段发生，投影未恢复。额外读回及CGAL检查不用于性能结论。

## 同输入预算对照

完整GPU倍率1/2/4三组均保留，实际简化入口vertices、faces和均值数组逐位相同，归一化源及物理源绑定；只改变作者目标面倍率，仍执行原简化和安全投影。下表为原始投影输出，还不是维护发布。

| 倍率 | 面数 | 体积mm³ | 双向面积样本0.1毫米内最低占比 | 反向顶点峰值mm | 低于10度面 |
|---|---|---|---|---|---|
{table}

面数增大，坏面数量也增大，比例降低；不能称每项质量都改善。相同第一阶段下预算增加改善该薄壁边缘保持，但该预算对照本身不是新算法创新，也不能证明一般曲面收益。

用同一冻结质量优先排斥方法、同一物理源、同一累计首刀工具和同一独立参照做维护，三组均保存后重新加载，冻结整面支撑、精确材料侧锚点、嵌入和源拓扑全部通过。

| 倍率 | 维护后体积mm³ | 双向面积样本0.1毫米内最低占比 | 低于10度面 | 保存复审 |
|---|---|---|---|---|
{maintained_table}

0.1毫米仅作分布参考线，不设最大误差或达标率门槛；顶点峰值、面积分位数、体积损失各自报告。未给出连续全表面距离或完整特征保持证书。三组静态GPU共3次，另有首次阶段观测1次；静态维护不新增GPU或父发布。

## 真实反馈

倍率4隔离入口从初态运行薄壁三事件，沿原父链发布规则；严格无变化复用机制保留，只有原始布尔源及准备源都逐坐标有向面重数相同才跳过求解，全部累计工具重新审查。

{outcomes}

新版本完整分母为3，不拼接123号旧版本的17/21。新批次摘要`{sha(bp)}`，保存复审摘要`{sha(qp)}`。真实连续结论仅限本路线已见开发输入，不把静态改善当作未见评价或最终交付。

## 证据与后续

- 同输入完整统计：`{comparison_path}`，SHA`{sha(comparison_path)}`。
- 新真实反馈：`{bp}`；保存复审：`{qp}`。
- 新资产：`{asset}`，全部文件绑定SHA，保留三组原始输出。
- 首次阶段观测25738、三预算89452/10090/2685及维护65174/22604/18701均退出0；真实反馈23976已终态。GPU实例保持开启。

后续根据真实反馈终态，处理后续编码源交叠和小特征保持，并围绕可归因的几何保护机制而非单纯固定加面构建算法。其他六家族、长序列、未见评价、连续几何和在线交付仍需完整验证，研究目标未完成。
'''
    with doc.open("x", encoding="utf8") as stream:
        stream.write(content)
    plan = project / "课题规划与专题调研/40-累计切削域排斥连续验证推进记录.md"
    lines = plan.read_text("utf8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("> **修改时间及修改内容**"):
            lines[index] = f"> **修改时间及修改内容**：{now}，补充{number}号薄壁同输入预算因果对照及倍率4新反馈。"
        if line.startswith("> **文档概述**"):
            lines[index] = f"> **文档概述**：薄壁边角损失主要在简化阶段；三预算实际简化输入逐位同一，提高预算改善形状但增加面数。倍率4新反馈{b['summary']['published']}/3，保存{q['summary']['passed']}/{q['summary']['saved_candidates']}通过，研究目标未完成。"
    plan.write_text("\n".join(lines) + f"\n修改时间及修改内容：{now}，新增薄壁同输入三简化预算完整GPU及首刀维护复审，全部三组保留；倍率4实际父反馈{b['summary']['published']}/3、保存复审通过。新版本不合并旧17/21；下一步几何保护机制与编码交叠，见组合验证{number}号。\n", "utf8")
    print(doc, flush=True)
    print(asset, flush=True)


if __name__ == "__main__":
    main()
