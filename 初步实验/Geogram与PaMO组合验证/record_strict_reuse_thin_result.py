"""保存严格无变化薄壁终态、复用资产和研究记录，不改写旧实验。"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil

import trimesh
from exact_oriented_surface_identity import exact_oriented_surface_identity


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    project = Path.cwd()
    here = project / "初步实验/Geogram与PaMO组合验证"
    root = Path("D:/GraduationProject_切削排斥证据")
    batch = root / "20261005_严格无变化复用薄壁三刀真实反馈"
    qa_path = root / "20261005_严格复用薄壁三保存独立复审/01-保存候选整面与材料侧独立复审.json"
    report_path = batch / "01-统一配置完整父反馈记录.json"
    report = json.loads(report_path.read_text("utf8"))
    qa = json.loads(qa_path.read_text("utf8"))
    assert report["status"] == "completed_with_recorded_outcomes" and report["summary"]["published"] == 3
    assert qa["status"] == "completed" and qa["summary"]["saved_candidates"] == qa["summary"]["passed"] == 3
    snapshot = here.parent / "Geogram与PaMO切削排斥冻结_20261005_严格无变化复用薄壁三刀反馈"
    frozen_manifest = snapshot / "01-执行源码冻结清单.json"
    assert digest(frozen_manifest) == report["snapshot_sha256"]
    for item in json.loads(frozen_manifest.read_text("utf8")):
        assert digest(snapshot / item["file"]) == item["sha256"]
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日%H时%M分%S秒")
    asset_root = root / "可复用磨削测试集"
    versions = [int(m.group(1)) for p in asset_root.iterdir() if (m := re.search(r"_v(\d+)$", p.name))]
    asset = asset_root / f"严格无变化布尔与累计工具复审_v{max(versions, default=0) + 1}"
    asset.mkdir(exist_ok=False)
    rid = report["selected_route"]
    first = batch / f"{rid}_e0_candidate_boolean/candidate.obj"
    mapping = [(first, "01-已发布首刀父网格.obj")]
    for index, event in enumerate(("e1", "e2")):
        folder = batch / f"{rid}_{event}_candidate_input"
        mapping += [(folder / "source.obj", f"{index * 3 + 2:02d}-{event}原始布尔源.obj"),
                    (folder / "labels.json", f"{index * 3 + 3:02d}-{event}原始来源.json"),
                    (batch / f"{rid}_{event}_candidate_boolean/01-严格无变化复用与累计工具复审.json", f"{index * 3 + 4:02d}-{event}累计工具证明.json")]
    for source, name in mapping:
        shutil.copyfile(source, asset / name)
    identity_tests = []
    parent = trimesh.load(first, force="mesh", process=False)
    for row in report["rows"][1:]:
        source_folder = batch / f"{rid}_{row['event']}_candidate_input"
        source = trimesh.load(source_folder / "source.obj", force="mesh", process=False)
        bits = json.loads((source_folder / "labels.json").read_text("utf8"))["operand_bits"]
        identity_tests.append({"event": row["event"], **exact_oriented_surface_identity(parent, source, bits)})
        assert identity_tests[-1]["same"] and row["output_sha256"] == digest(first)
    proof = {"生成时间": now, "修改时间及修改内容": "首次生成，冻结真实复用证据与逐文件摘要",
             "文档概述": "两次原始布尔源严格相同，复用保留全部累计工具重审，不按距离容差复用",
             "索引目录": ["files", "identity_tests", "summary"],
             "files": [{"file": name, "sha256": digest(asset / name), "origin": str(source)} for source, name in mapping],
             "identity_tests": identity_tests, "summary": report["summary"],
             "saved_audit_summary": qa["summary"], "batch_sha256": digest(report_path),
             "saved_audit_sha256": digest(qa_path), "snapshot_manifest_sha256": digest(frozen_manifest)}
    (asset / "08-复用资产绑定清单.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), "utf8")
    numbers = [int(m.group(1)) for p in here.glob("*.md") if (m := re.match(r"(\d+)-", p.name))]
    number = max(numbers, default=0) + 1
    doc = here / f"{number:02d}-严格无变化复用薄壁三刀终态与累计工具独立复审.md"
    fractions = [r["cumulative_distribution"]["minimum_bidirectional_area_fraction_within_0_1_mm"] * 100 for r in report["rows"]]
    content = f'''# 严格无变化复用薄壁三刀终态与累计工具独立复审

> 生成时间：{now}（北京时间）
> 修改时间及修改内容：{now}，首次生成；记录新冻结版本薄壁终态，旧1/3负例保持不变。
> 文档概述：薄壁新三刀3/3观察发布、3/3保存复审；完整GPU调用1次，另2次严格无变化复用。首刀形状尾部仍保留，六其他家族同版本开发正在执行，整体目标未完成。
> 索引目录：[结果](#结果) · [复用条件](#复用条件) · [统计与边界](#统计与边界) · [证据](#证据) · [下一步](#下一步)

## 结果

| 事件 | 实际执行 | 输出与父绑定 | 独立保存复审 |
|---|---|---|---|
| e0 | 完整三阶段GPU与排斥维护 | 新发布 | 通过 |
| e1 | 严格无变化复用，累计2工具重审 | 原文件SHA完全相同 | 通过 |
| e2 | 严格无变化复用，累计3工具重审 | 原文件SHA完全相同 | 通过 |

完整分母为3事件，不把两次复用称为新GPU求解、质量改善或GPU加速。该输入此前已用于诊断与开发，不能称独立未见评价。

121号旧最低R256批次为1/3发布，第二刀布尔结果严格没变却再次求解收缩并拒绝。本版阻止重复维护；旧拒绝与第三刀阻断不改写。本轮首刀输出SHA为`{digest(first)}`，三事件保存文件相同。第二、第三刀虽然参考网格三角化不同，实际父反馈的布尔输出完全没变。

## 复用条件

原始布尔源及准备后物理源都必须仅含父来源1，逐个保存浮点坐标的有向三角形多重集合严格相同。只消除面循环起点、面排列与顶点编号差异，不使用任何距离容差，不忽略反向面或面重数。

复制父文件后重新做完整CGAL EPECK闭合嵌入检查、有限性、非退化、朝向与流形审查、源拓扑保持；对当前事件全部累计凸工具重新证明每张整三角面支撑排斥，并以精确材料侧分类器证明工具内部锚点在材料外。任何复审失败均拒绝本次复用。工具历史由原冻结清单及事件前缀重新构建，后续改变事件仍调用完整GPU原路径。

新增3项身份判断单元测试通过：重编号及有向循环面匹配；反向或重复面拒绝；仅一浮点单位坐标变化或工具来源拒绝。实际保存独立复审3/3通过，重新核对父链、源/标签、工具/参照摘要、冻结支撑及新材料侧分类。

## 统计与边界

三事件双向面积样本0.1毫米内最低占比分别为{fractions[0]:.6f}%、{fractions[1]:.6f}%、{fractions[2]:.6f}%；该比例为面积随机抽样估计，不是全表面连续界。三事件保存坐标相同而独立参照三角化不同，因此统计分布存在轻微差异。

首刀仍有约0.83毫米的局部边角尾部，与用户接受的历史0.138毫米案例不是同一个误差。没有新增固定最大误差或达标率门槛。634面中低于10度24面（3.785489%）、低于5度3面、低于1度0面；25度且q≥0.4的高质量面532（83.911672%）。复用保持这些值，没有解决首刀薄壁体积损失和小特征保持。

## 证据

- 完整批次：`{report_path}`，SHA `{digest(report_path)}`。
- 保存独立复审：`{qa_path}`，SHA `{digest(qa_path)}`。
- 数值快照：`{snapshot}`，清单SHA `{digest(frozen_manifest)}`；所有清单文件本轮重验一致。
- 新复用资产：`{asset}`，两次原始源身份回归通过，逐文件SHA绑定。
- 实际进程：薄壁GPU主进程24529与保存复审均退出0；六其他家族控制进程65142继续运行。

## 下一步

正在同一个数值版本上从初态执行板体、球体、椭球、弯曲骨样体、贯通孔、窄缝六路线18事件，保留每个失败和阻断；结合本轮薄壁形成七家族21事件完整分母。不能拼接旧方向修复版本的成功数。其后继续定位首刀阶段二/三薄壁边缘损失，并做小特征与长序列保持。一般曲面连续几何、未见评价及在线交付仍未完成。
'''
    with doc.open("x", encoding="utf8") as stream:
        stream.write(content)
    plan = project / "课题规划与专题调研/40-累计切削域排斥连续验证推进记录.md"
    text = plan.read_text("utf8")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("> **修改时间及修改内容**"):
            lines[index] = f"> **修改时间及修改内容**：{now}，补充{number}号严格无变化薄壁3/3及保存3/3复审，六其他家族同版本继续执行。"
        if line.startswith("> **文档概述**"):
            lines[index] = "> **文档概述**：严格无变化复用避免重复求解收缩，薄壁三刀3/3；完整GPU1次、严格复用2次。首刀约0.83毫米尾部及体积损失仍保留，同版本六家族在运行，研究目标未完成。"
    text = "\n".join(lines) + f"\n修改时间及修改内容：{now}，本轮薄壁3/3观察发布、3/3保存独立复审；严格原始布尔源与准备源有向面重数相同才复用，全部累计工具重审。完整GPU1次、复用2次，首刀形状缺口仍待解决。详见组合验证{number}号；六其他家族18事件句柄65142运行，不能混合旧版本计数。\n"
    plan.write_text(text, "utf8")
    print(doc, flush=True)
    print(asset, flush=True)


if __name__ == "__main__":
    main()
