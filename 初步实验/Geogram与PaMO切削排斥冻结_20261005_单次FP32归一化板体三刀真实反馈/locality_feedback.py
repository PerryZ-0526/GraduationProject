"""局部维护失败时扩域一次，再全量回退；独立审计后才发布新父版本。"""

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from time import perf_counter


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def maintain_frame(parent, source, build, audit, source_accepted):
    """构建器接收同一布尔输入与分支，审计器核查文件后返回有效性证据。"""
    start = perf_counter()
    source = Path(source)
    previous = dict(parent)
    if digest(previous["mesh"]) != previous["sha256"]:
        raise ValueError("已发布父快照发生变化")
    source_sha = digest(source)
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "parent_version": previous["version"], "parent_sha256": previous["sha256"],
              "source_sha256": source_sha, "attempts": [], "published": False,
              "acceptance_scope": "独立拓扑与离散几何抽样；不代表连续几何证书"}
    state = previous
    if source_accepted:
        for method, rings in (("boolean", 0), ("boolean", 2), ("full", None)):
            attempt_start = perf_counter()
            attempt = {"method": method, "rings": rings, "accepted": False}
            try:
                # 每次重试都从同一布尔输入开始，失败候选不能成为下一次的父网格。
                candidate = Path(build(source, method, rings))
                if candidate.resolve() in (source.resolve(), Path(previous["mesh"]).resolve()):
                    raise ValueError("候选必须另存，不能覆盖输入或父快照")
                candidate_sha = digest(candidate)
                evidence = audit(candidate, method, rings)
                required = ("topology_passed", "sampled_geometry_passed", "vertex_manifold",
                            "finite_nondegenerate", "capacity_unchanged")
                accepted = all(evidence.get(key) is True for key in required)
                if method == "boolean":
                    accepted = accepted and evidence.get("fixed_contract_passed") is True
                if digest(candidate) != candidate_sha:
                    raise ValueError("独立审计期间候选发生变化")
                attempt.update(accepted=accepted, evidence=evidence, candidate=str(candidate),
                               candidate_sha256=candidate_sha)
            except Exception as error:
                attempt["error"] = str(error)
            # 即使构建或审计报错，也必须核对已发布状态和原始输入没有被污染。
            if digest(previous["mesh"]) != previous["sha256"] or digest(source) != source_sha:
                raise ValueError("构建或审计修改了父快照或布尔输入，停止发布")
            attempt["maintenance_and_audit_ms"] = (perf_counter() - attempt_start) * 1000
            report["attempts"].append(attempt)
            if attempt["accepted"]:
                state = {"mesh": attempt["candidate"], "sha256": attempt["candidate_sha256"],
                         "version": previous["version"] + 1}
                report["published"] = True
                break
    else:
        report["reason"] = "上游输入未通过有效性检查，不启动局部或全量维护"
    report["published_version"] = state["version"]
    report["expansion_count"] = sum(a["method"] == "boolean" and a["rings"] == 2 for a in report["attempts"])
    report["full_fallback_count"] = sum(a["method"] == "full" for a in report["attempts"])
    report["total_ms"] = (perf_counter() - start) * 1000
    return state, report
