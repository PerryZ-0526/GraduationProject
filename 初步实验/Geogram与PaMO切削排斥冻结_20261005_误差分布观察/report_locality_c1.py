"""汇总三批真实局部C1开发，保留全部拒绝与阻断，不把复跑当独立样本。"""

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from locality_feedback import digest

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "实验结果"


def main():
    destination = HERE / "31-布尔局部维护真实反馈与数值碎片诊断.md"
    if destination.exists():
        raise FileExistsError(destination)
    names = ("20261004_局部维护六路线C1开发", "20261004_局部维护六路线C1开发_来源清理",
             "20261004_局部维护六路线C1开发_清理与复用")
    summary = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(), "batches": []}
    tables = []
    for index, name in enumerate(names):
        folder = RESULTS / name
        execution_path = folder / "01-局部C1逐帧执行与独立审计.json"
        audit_path = folder / "03-C1父链与离散距离区间复核.json"
        execution = json.loads(execution_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if execution["status"] != "completed_with_recorded_failures" or audit["status"] != "completed":
            raise ValueError("批次或复核尚未结束")
        if digest(execution_path) != audit["execution_sha256"]:
            raise ValueError("审计对应的执行记录改变")
        counts = dict(Counter(r["status"] for r in execution["rows"]))
        routes = []
        for route in dict.fromkeys(r["route"] for r in execution["rows"]):
            rows = [r for r in execution["rows"] if r["route"] == route]
            published = sum(r["status"] == "accepted_sampled" for r in rows)
            reused = sum(r["status"] == "contained_reused" for r in rows)
            routes.append({"route": route, "published": published, "reused": reused, "planned": len(rows),
                           "full_coverage": published + reused == len(rows)})
        expansions = sum(r.get("control", {}).get("expansion_count", 0) for r in execution["rows"])
        fallback = sum(r.get("control", {}).get("full_fallback_count", 0) for r in execution["rows"])
        interval_passed = sum(r["within_0_1_under_exact_query_assumption"] for r in audit["rows"])
        summary["batches"].append({"name": name, "counts": counts, "routes": routes,
            "expansions": expansions, "full_fallbacks": fallback, "audited_outputs": len(audit["rows"]),
            "exact_query_conditional_interval_passed": interval_passed,
            "candidate_topology_passed": sum(r["topology_matches_expected"] for r in audit["rows"]),
            "execution_sha256": digest(execution_path), "audit_sha256": digest(audit_path)})
        tables.append(f"| {index + 1} | {counts.get('accepted_sampled', 0)}/24 | {counts.get('retained_parent_and_stopped', 0)} | "
                      f"{counts.get('blocked_by_previous_failure', 0)} | {sum(r['full_coverage'] for r in routes)}/6 | {expansions}/{fallback} |")
    third = summary["batches"][-1]
    route_table = ["| 路线 | 新发布/计划 | 完整覆盖 |", "|---|---:|---|"]
    for route in third["routes"]:
        route_table.append(f"| {route['route']} | {route['published']}/{route['planned']} | {'是' if route['full_coverage'] else '否'} |")
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日%H时%M分%S秒")
    content = f"""# 31-布尔局部维护真实反馈与数值碎片诊断

> **生成时间**：{now}（北京时间）  
> **修改时间及修改内容**：{now}，首次生成；记录六路线真实局部C1、来源同步清理、重复扫掠复用、父版本核对与离散距离区间复核。  
> **文档概述**：发布控制已连接实际GPU维护与逐帧父网格反馈。三批运行均保留原计划分母；最新批次只有一条路线完整覆盖，数值碎片和未排除报警仍阻断其他路线。没有得到一般连续有效性或质量匹配效率优势。  
> **索引目录**：[一、实现与冻结](#一实现与冻结) · [二、真实反馈结果](#二真实反馈结果) · [三、数值碎片与来源](#三数值碎片与来源) · [四、独立复核的范围](#四独立复核的范围) · [五、验证与剩余工作](#五验证与剩余工作)

## 一、实现与冻结

`run_locality_c1.py`使用9月28日冻结的六条开发路线及24个切削前缀。每帧从上一张已接受输出做Geogram禁共面简化布尔，导出面来源；取回核查合法性和来源后调用GPU。维护依次允许0层局部、一次2层扩域、完整PaMO回退；任一候选须取回本机独立审计，接受后才递增父版本。所有尝试失败或输入非法时保留上一父快照，阻断该路线后续帧。其他路线继续，失败未删除。

继续使用已构建的固定掩码CUDA副本、八次折叠上限及作者五轮安全投影。完整网格BVH与碰撞检查保持；17位有效数字OBJ导出和重载后固定域契约逐帧核对。代码快照、父/工具/候选/来源与二进制哈希进入原始记录。凭据不进入代码快照与报告。设备与环境沿用30号记录。

第一批使用原始布尔输入；第二批统一使用基线八位坐标去重，保留面来源。前两批尚未接入已包含胶囊的重复复用，因此它们是额外重复处理的开发诊断，不是含复用策略的完整协议对照。第三批加入既有等半径胶囊包含规则：重复时复用父快照，不再次布尔或优化，不递增网格版本；本次重复路线在复用事件前就被拒绝，实际未触发复用。复用策略本身不证明PaMO重复运行零漂移。

## 二、真实反馈结果

| 批次 | 新发布/计划 | 输入拒绝 | 后续阻断 | 完整路线 | 扩域/全量回退 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(tables)}

最新批次逐路线结果：

{chr(10).join(route_table)}

三批共生成30张GPU候选，全部在首个0层尝试通过列明的有效性检查；没有真实GPU扩域或全量回退的触发证据。控制器的失败分支仍以8项失败注入测试证明，不能用无触发批次冒充实际回退覆盖。各批为一次运行，不能把30张或重复路线当独立样本数。

第一帧同输入复跑也会产生不同维护输出，继而产生不同后续布尔碎片。因此9→10→11张的计数变化不能单独归因于清理或复用。该三批没有随机交错、三次路线级配对或完整PaMO质量匹配对照，不作性能或来源贡献推断。记录的整帧时间包含SSH、传输及独立审计，不含显示，仍不是产品端到端延迟。

## 三、数值碎片与来源

第一批五个拒绝输入分别有49—53个面积不超过1e-12平方毫米的面，FP32也有退化；并非只有自交报警。停钻e1的一张报警面面积约7.53e-17平方毫米。原始网格保持闭合及欧拉数2，但这种数值表示不能直接交给当前PaMO局部算子。

`locality_cleanup.py`复用基线八位坐标键合并顶点，只删除合并后具有重复顶点的面，同步筛选原始来源序号，禁止来源冲突的重复面；去重位移沿用1e-7毫米预算。仍有三个不同顶点的细面保留并继续门控，不把删除坏面后的孔洞当作合法输入。原始OBJ和来源不覆盖，清理副本重新做拓扑、FP32、来源及独立参照审计。

第一批五个拒绝输入的只读清理删除46—54个折叠面，部分仍有近退化面或报警。最新批次的四条板体路线在e1分别保留5/7/6/2个近退化面；停钻路线e5没有退化，但仍有2面报警，因此停止。第一批分离轴复核后的五个输入仍有未排除报警，没有把报警直接解释为已证明自交，也没有恢复其后续计数。

## 四、独立复核的范围

`audit_locality_c1.py`核查冻结代码、真实父哈希和逐帧版本，拒绝帧保持父状态，接受帧单次递增，并检查候选闭合分量及欧拉数。30张输出均通过该后验父链和预期拓扑核对。

30张输出对冻结的解析离散参照均完成双向自适应数值距离区间；在距离查询精确的假设下，上界不超过0.1毫米。它们不是连续几何证书：VTK浮点查询误差没有认证，参照离散误差也未知；不能用接近0.1毫米的计算上界断言真实解析或解剖几何误差已严格小于0.1毫米。该复核为后验检查，不能改写发布时只有面积抽样的事实。

原始记录位于三批同名结果目录的`01-局部C1逐帧执行与独立审计.json`及`03-C1父链与离散距离区间复核.json`。第一批另有`02-阻断输入分离轴复核.json`与`04-原阻断输入来源清理只读诊断.json`。统计保存在最新目录的`05-C1批次统计.json`。

## 五、验证与剩余工作

首次来源清理4项测试纳入统一核心后，核心实际103项通过、20组无失败，Geogram适配器类级跳过1次。自查后将去重预算检查移至删除孤立顶点后的最终副本，并新增空网格拒绝回归，来源清理5项通过；未重复运行整个核心。对两批全部31张最终清理副本追加只读预算复核，最大原顶点到最终副本顶点距离约7.61e-9毫米，全部低于1e-7毫米。旧GPU批次代码快照和数字保留，证据见`06-最终清理副本顶点预算复核.json`。此前控制器8项及固定边界5项测试继续保留。当前局部C1执行器的成功与输入拒绝路径已用真实GPU验证；没有宣称所有失败分支都实测触发。

下一步先处理保持来源、拓扑与几何预算的近退化碎片重三角化，再在六条开发路线统一验证；仍须解决活动域内质量损失。原12条路线已被29号基线体检查看，新机制独立评测须另冻结未见输入。新局部CT16段及138段、连续输入发布状态年龄、完整公平配对性能和连续几何界仍未完成。目标保持进行中，不用一条成功短路线代替完整交付。
"""
    save_path = RESULTS / names[-1] / "05-C1批次统计.json"
    save_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    destination.write_bytes(content.encode("utf-8"))
    print(destination)


if __name__ == "__main__":
    main()
