"""切削排斥开发续验：独立参照恢复，按完整输入及原执行代码摘要复用GPU原始输出。"""

import json
from pathlib import Path
import shutil

import run_constrained_feedback as controller
import run_cut_exclusion_feedback as first
from run_cut_exclusion_continuation import CertifiedCutEngine, audit
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from study_cut_exclusion import input_valid
from exact_alarm_contact import mesh_valid_exact_contacts
from locality_cleanup import clean_provenance
from locality_diagnostic import source_region, verify_labels
from independent_reference_recovery import recover_reference

PREVIOUS = HERE.parent / "Geogram与PaMO组合验证/实验结果/20261004_切削排斥四路线三刀GPU父反馈"
ORIGINAL_RUN = RemoteQuality.run


class RecoveryCutEngine(CertifiedCutEngine):
    def setup(self):
        info = super().setup()
        info.update(reference_recovery="initial_and_frozen_tool_sequential_replay_then_1e_7_probe_and_exact_embedding",
                    previous_gpu_report_sha256=sha256(PREVIOUS / "01-反馈执行与独立审计.json"),
                    recovery_entry_sha256=sha256(Path(__file__)),
                    reuse_policy="same_source_labels_tool_and_five_worker_source_hashes_only")
        save(self.output / "04-参照恢复与GPU复用冻结.json", {"生成时间": now(),
             "修改时间及修改内容": "首次生成，先于续验结果", "文档概述": "显式参照恢复及原始GPU输出复用",
             "索引目录": ["environment"], "environment": info})
        return info


def cached_run(engine, source, labels, tool, method, folder):
    prior = json.loads((PREVIOUS / "01-反馈执行与独立审计.json").read_text("utf8"))
    same_code = prior["environment"]["code_sha256"] == {
        name: sha256(HERE / name) for name in prior["environment"]["code_sha256"]}
    inputs = {name: sha256(path) for name, path in (("source.obj", source), ("labels.json", labels), ("tool.obj", tool))}
    stem = Path(folder).name
    for row in prior["rows"]:
        for attempt in row.get("attempts", []):
            previous_stem = f"{row['route']}_{row['event']}_{row['branch']}_{attempt['method']}"
            if previous_stem != stem or attempt["execution"]["returncode"] or not same_code or attempt["inputs_sha256"] != inputs:
                continue
            previous = PREVIOUS / stem
            raw = previous / "raw_full_candidate.obj"
            expected = attempt.get("raw_full_output_sha256")
            if not raw.exists():
                raw = previous / "candidate.obj"
                expected = attempt["output_sha256"]
            if sha256(raw) != expected:
                raise ValueError("旧GPU原始输出摘要改变，不能复用")
            destination = Path(folder)
            destination.mkdir(parents=True)
            # 缓存没有启动工作进程，仍须为后续保存网格审计创建独立远端目录。
            if execute(engine.client, ["mkdir", engine.remote + "/" + stem])["returncode"]:
                raise RuntimeError("GPU复用审计目录无法创建")
            shutil.copyfile(raw, destination / "candidate.obj")
            for name in ("details.json", "worker.log"):
                shutil.copyfile(previous / name, destination / name)
            return {**json.loads((destination / "details.json").read_text("utf8")),
                    "method": method, "execution": {"returncode": 0, "remote_roundtrip_ms": None},
                    "inputs_sha256": inputs, "output_sha256": sha256(raw),
                    "gpu_execution_reused_from": str(raw), "gpu_execution_not_repeated": True}
    return ORIGINAL_RUN(engine, source, labels, tool, method, folder)


def exact_recovery(engine, prepared, route, event, initial_remote, folder, reuse):
    mesh, record = recover_reference(engine, prepared, route, event, initial_remote, folder, reuse)
    if mesh is None:
        return mesh, record
    path = folder / "validated_reference.obj"
    remote = engine.remote + "/" + folder.name + "_validated_for_embedding.obj"
    engine.sftp.put(str(path), remote)
    if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
        raise ValueError("恢复参照上传摘要不一致")
    run = execute(engine.client, [CHECKER, remote])
    exact = json.loads(run["stdout"].strip()) if not run["returncode"] else {"execution": run}
    record["exact_saved_embedding"] = exact
    if not exact.get("embedded_closed", False):
        # 保留被拒绝的保存对象，但禁止后续算子按认证文件名误用它。
        path.rename(folder / "rejected_validated_reference.obj")
        record.update(accepted=False, status="recovered_reference_exact_embedding_rejected")
        return None, record
    return mesh, record


if __name__ == "__main__":
    # 仅新入口启用恢复及缓存；旧失败终态与正在运行的其他分支保持不变。
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--split", required=True)
    args = parser.parse_args()
    RecoveryCutEngine.prepared = args.prepared
    RemoteQuality.run = cached_run
    controller.RemoteQuality = RecoveryCutEngine
    controller.REFERENCE_RECOVERY = exact_recovery
    controller.mesh_valid = input_valid
    controller.VALID_SOURCE_BITS = (1, 2, 3)
    controller.clean_provenance = lambda mesh, bits: clean_provenance(mesh, bits, allow_shared=True)
    controller.source_region = lambda mesh, bits: source_region(mesh, bits, allow_shared=True)
    controller.verify_labels = lambda *values: verify_labels(*values, allow_shared=True)
    first.mesh_valid = mesh_valid_exact_contacts
    controller.audit_candidate = audit
    controller.main()
