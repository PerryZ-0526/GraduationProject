"""同父同工具共用布尔输入与原版GPU输出，父链分歧后各自独立运行切削排斥。"""

import argparse
import json
from pathlib import Path
import shutil

import run_constrained_feedback as controller
import run_cut_exclusion_feedback as first
from run_cut_exclusion_continuation import CertifiedCutEngine, audit
from run_cut_exclusion_recovery import exact_recovery
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256
from study_cut_exclusion import input_valid
from exact_alarm_contact import mesh_valid_exact_contacts
from locality_cleanup import clean_provenance
from locality_diagnostic import source_region, verify_labels

ORIGINAL_GPU_RUN = RemoteQuality.run
CSG_CACHE = {}
GPU_CACHE = {}


class PairedCutEngine(CertifiedCutEngine):
    def setup(self):
        info = super().setup()
        info.update(paired_input_policy="equal_parent_and_tool_share_CSG_then_equal_source_labels_tool_share_raw_GPU",
                    paired_entry_sha256=sha256(Path(__file__)),
                    reference_recovery="independent_initial_tool_replay_plus_exact_saved_embedding",
                    timing_scope="shared_GPU_cost_is_counted_once_not_candidate_speedup")
        save(self.output / "05-同输入配对与参照协议冻结.json", {"生成时间": now(),
             "修改时间及修改内容": "首次生成，先于保留输入候选输出", "文档概述": "排除同父输入三角化差异，不改变算法预算",
             "索引目录": ["environment"], "environment": info})
        return info


def shared_csg(client, argv, log=None, timeout=120):
    if argv[0] != controller.PROVENANCE:
        return execute(client, argv, log, timeout)
    hashes = [execute(client, ["sha256sum", path])["stdout"].split()[0] for path in argv[1:3]]
    key = (*hashes, *argv[5:])
    if key not in CSG_CACHE:
        result = execute(client, argv, log, timeout)
        if not result["returncode"]:
            CSG_CACHE[key] = (argv[3], argv[4], log)
        return result
    source, labels, previous_log = CSG_CACHE[key]
    for previous, destination in ((source, argv[3]), (labels, argv[4]), (previous_log, log)):
        if execute(client, ["cp", previous, destination])["returncode"]:
            raise RuntimeError("同父布尔输入复用失败")
    return {"returncode": 0, "remote_roundtrip_ms": None, "command": "equal_parent_tool_CSG_reuse",
            "reused_source": source, "reused_labels": labels, "parent_tool_sha256": hashes}


def shared_gpu(engine, source, labels, tool, method, folder):
    identities = {name: sha256(path) for name, path in (("source.obj", source), ("labels.json", labels), ("tool.obj", tool))}
    key = tuple(sorted(identities.items()))
    folder = Path(folder)
    if key not in GPU_CACHE:
        row = ORIGINAL_GPU_RUN(engine, source, labels, tool, method, folder)
        if not row["execution"]["returncode"]:
            # 在任何CPU修正之前保存原始GPU结果，后续分支只能复用此不可变对象。
            raw = folder / "raw_for_equal_input_reuse.obj"
            shutil.copyfile(folder / "candidate.obj", raw)
            GPU_CACHE[key] = (raw, sha256(raw), folder, dict(row))
        return row
    raw, expected, previous, row = GPU_CACHE[key]
    if sha256(raw) != expected:
        raise ValueError("同输入GPU缓存对象已改变")
    folder.mkdir(parents=True)
    if execute(engine.client, ["mkdir", engine.remote + "/" + folder.name])["returncode"]:
        raise RuntimeError("同输入GPU缓存的审计目录无法创建")
    shutil.copyfile(raw, folder / "candidate.obj")
    for name in ("worker.log", "details.json"):
        shutil.copyfile(previous / name, folder / name)
    return {**row, "inputs_sha256": identities, "output_sha256": expected,
            "execution": {"returncode": 0, "remote_roundtrip_ms": None, "kind": "same_input_raw_GPU_reuse"},
            "gpu_execution_not_repeated": True, "gpu_execution_reused_from": str(raw)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--split", required=True)
    args = parser.parse_args()
    PairedCutEngine.prepared = args.prepared
    RemoteQuality.run = shared_gpu
    controller.execute = shared_csg
    controller.RemoteQuality = PairedCutEngine
    controller.REFERENCE_RECOVERY = exact_recovery
    controller.mesh_valid = input_valid
    controller.VALID_SOURCE_BITS = (1, 2, 3)
    controller.clean_provenance = lambda mesh, bits: clean_provenance(mesh, bits, allow_shared=True)
    controller.source_region = lambda mesh, bits: source_region(mesh, bits, allow_shared=True)
    controller.verify_labels = lambda *values: verify_labels(*values, allow_shared=True)
    first.mesh_valid = mesh_valid_exact_contacts
    controller.audit_candidate = audit
    controller.main()
