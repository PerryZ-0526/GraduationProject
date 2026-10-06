"""记录原始目标提案新薄壁完整终态，不拼接上一版本七家族分母。"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    project = Path.cwd()
    root = Path("D:/GraduationProject_切削排斥证据")
    bp = root / "20261005_原始顶点局部提案薄壁三刀真实反馈/01-统一配置完整父反馈记录.json"
    qp = root / "20261005_原始目标薄壁三保存独立复审/01-保存候选整面与材料侧独立复审.json"
    b, q = json.loads(bp.read_text("utf8")), json.loads(qp.read_text("utf8"))
    assert b["status"] == "completed_with_recorded_outcomes" and b["summary"]["published"] == 3
    assert q["status"] == "completed" and q["summary"]["saved_candidates"] == q["summary"]["passed"] == 3
    assert q["source_batch_sha256"] == sha(bp)
    snapshot = project / "初步实验/Geogram与PaMO切削排斥冻结_20261005_原始顶点局部提案薄壁反馈"
    assert sha(snapshot / "01-执行源码冻结清单.json") == b["snapshot_sha256"]
    for item in json.loads((snapshot / "01-执行源码冻结清单.json").read_text("utf8")):
        assert sha(snapshot / item["file"]) == item["sha256"]
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日%H时%M分%S秒")
    here = project / "初步实验/Geogram与PaMO组合验证"
    number = max(int(m.group(1)) for p in here.glob("*.md") if (m := re.match(r"(\d+)-", p.name))) + 1
    doc = here / f"{number:02d}-原始目标两点局部修正薄壁三刀完整反馈与保存复审.md"
    projection = b["rows"][2]["attempt"]["cut_exclusion"]["raw_seed_projection"]
    table = "\n".join(f"| {r['event']} | {r['execution_role']} | {r['attempt']['quality']['total_faces']} | {r['cumulative_distribution']['minimum_bidirectional_area_fraction_within_0_1_mm'] * 100:.6f}% | {r['cumulative_distribution']['vertices_reverse']['max_mm']:.6f} | {r['attempt']['quality']['angle_below_10_deg']['faces']}（{r['attempt']['quality']['angle_below_10_deg']['fraction'] * 100:.6f}%） |" for r in b["rows"])
    content = f'''# 原始目标两点局部修正薄壁三刀完整反馈与保存复审

> 生成时间：{now}（北京时间）
> 修改时间及修改内容：{now}，首次生成；结算新原始顶点目标提案版本三刀，旧版本2/3保持。
> 文档概述：同版新薄壁3/3观察发布，3/3保存独立复审通过；2次完整GPU、1次严格复用，第三刀只动2点。其他六家族18事件同版验证13866运行中，目标未完成。
> 索引目录：[实际结果](#实际结果) · [发布与复审](#发布与复审) · [证据与后续](#证据与后续)

## 实际结果

| 事件 | 执行 | 面数 | 双向面积样本0.1毫米内最低占比 | 反向顶点峰值mm | 低于10度面 |
|---|---|---|---|---|---|
{table}

e0沿原合法提案发布；e1布尔源及准备源都与已发布父严格相同，补充自身法向后重审累计工具、原文件复用；e2改变几何，完整GPU求解后旧参照种子提案没有合法输出，触发唯一一次原始顶点目标局部提案。实际移动{projection['moved_vertices']}点，最大{projection['max_displacement_mm']:.9f}毫米，面连接保持。不能把本次新原始GPU网格与125号静态原始网格当作同一个输入；两者摘要和面数不同，直接静态因果仅限各自固定输入。

倍率4、最低SDF256和FP64三角输入保持上一版本，新增算法步骤只是原有提案无合法输出后的一次原始目标修正，完整预算显式冻结为1；未新增GPU调用或原版回退。误差仍按面积分布、顶点尾部和质量分别报告，不设固定最大值或达标率。修正预算0.1毫米约束该提案相对原GPU输入的位移，不是累计真实目标误差门槛。

## 发布与复审

每刀保存后独立读取实际文件，核对真实父链、物理源/来源标签、所有累计工具、独立参照及输出摘要。复用事件重新以有理数检查全部新增支撑的工具包含性；原始目标事件用其自身冻结支撑编号，禁止套用失败参照提案。三事件全部整面支撑、精确材料侧锚点、全量嵌入、有限非退化及源拓扑审查通过。

3/3仅为这条已见薄壁开发路线的连续观察，不把125号其他六家族16/18与本版3/3拼成同版本19/21。均匀面积样本比例是估计，100%样本通过不等于连续距离证书、特征保持或目标研究完成。

## 证据与后续

- 完整记录：`{bp}`，SHA`{sha(bp)}`。
- 保存复审：`{qp}`，SHA`{sha(qp)}`。
- 数值快照：`{snapshot}`，清单SHA`{b['snapshot_sha256']}`；本轮全部文件重验一致。
- GPU主进程35069及保存复审36918退出0；新六家族控制13866已启动，目录`D:/GraduationProject_切削排斥证据/20261005_原始顶点提案同版六家族18事件完整开发`。

后续收齐同一版完整21事件及保存复审，再处理两个独立参照拒绝；继续研究倍率4面数累乘问题、有界预算、长序列及小特征保持。完整连续几何与在线交付仍未完成，不关闭用户GPU，不改另一分支作者安装。
'''
    with doc.open("x", encoding="utf8") as stream:
        stream.write(content)
    plan = project / "课题规划与专题调研/40-累计切削域排斥连续验证推进记录.md"
    lines = plan.read_text("utf8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("> **修改时间及修改内容**"):
            lines[i] = f"> **修改时间及修改内容**：{now}，补充{number}号原始目标薄壁新3/3及保存3/3复审，其他六家族同版运行。"
        if line.startswith("> **文档概述**"):
            lines[i] = "> **文档概述**：原始目标唯一附加提案将薄壁新三刀推进至3/3，保存复审3/3；实际2次完整GPU、1次严格复用，第三刀只动2点。其他六家族13866仍运行，未拼接旧版本19/21，目标未完成。"
    plan.write_text("\n".join(lines) + f"\n修改时间及修改内容：{now}，原始目标提案新薄壁3/3发布及3/3独立保存复审，第三刀局部两点最大约{projection['max_displacement_mm']:.9f}毫米；六家族18事件13866同版GPU运行，见组合验证{number}号。\n", "utf8")
    print(doc, flush=True)


if __name__ == "__main__":
    main()
