"""切削排斥分支的新连续入口：显式共同来源协议、全网格精确嵌入发布门槛。"""

import argparse
from pathlib import Path
import json

import run_constrained_feedback as controller
import run_cut_exclusion_feedback as first
from run_adaptive_cut_feedback import AdaptiveCutEngine
from run_cut_exclusion_feedback import audit_exclusion
from run_constrained_batch import HERE
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from exact_alarm_contact import mesh_valid_exact_contacts
from study_cut_exclusion import input_valid
from locality_cleanup import clean_provenance
from locality_diagnostic import source_region, verify_labels


class CertifiedCutEngine(AdaptiveCutEngine):
    def setup(self):
        info = super().setup()
        # 核对实际上传的执行源码，不能以编译后读取的本机摘要代替远端证据。
        actual = {name: execute(self.client, ["sha256sum", self.remote + "/" + name])["stdout"].split()[0]
                  for name in info["code_sha256"]}
        if actual != info["code_sha256"]:
            raise ValueError("实际远端执行源码不符合本批冻结")
        info.update(actual_remote_code_sha256=actual,
                    exact_embedding_checker_sha256=execute(self.client, ["sha256sum", CHECKER])["stdout"].split()[0],
                    continuation_entry_sha256=sha256(Path(__file__)),
                    common_source_policy="retain_bit_3_and_verify_both_operand_surfaces",
                    actual_parameters={"pamo": "original_full_three_stages_once_per_branch_prefix",
                        "correction_budget_mm": .1, "clearance_mm": 1e-8, "max_refinement_levels": 2,
                        "geometry": "independent_cumulative_reference_8192_area_samples_and_all_vertices",
                        "candidate_attempts": 1, "fallback": "none",
                        "embedding": "CGAL_EPECK_all_faces_before_parent_feedback"})
        save(self.output / "03-实际分支协议冻结.json", {"生成时间": now(),
             "修改时间及修改内容": "首次生成，先于候选输出", "文档概述": "独立于控制器旧模板参数的真实执行协议",
             "索引目录": ["environment"], "environment": info})
        return info

    def run(self, source, labels, tool, method, folder):
        row = super().run(source, labels, tool, method, folder)
        if row["execution"]["returncode"]:
            return row
        path = Path(folder) / "candidate.obj"
        remote = self.remote + "/" + Path(folder).name + "/saved_for_embedding_audit.obj"
        self.sftp.put(str(path), remote)
        if execute(self.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
            raise ValueError("精确嵌入复核文件的实际摘要不匹配")
        run = execute(self.client, [CHECKER, remote], timeout=120)
        row["exact_embedding"] = {"execution": run, "saved_sha256": sha256(path)}
        if not run["returncode"]:
            row["exact_embedding"].update(json.loads(run["stdout"].strip()))
        save(Path(folder) / "04-保存网格全量精确嵌入审计.json", row["exact_embedding"])
        return row


def audit(source, tool, labels, folder, row):
    row = audit_exclusion(source, tool, labels, folder, row)
    # 两分支采用相同嵌入门槛；未通过时禁止作为下一刀父输入。
    if row["status"] == "accepted_sampled" and not row.get("exact_embedding", {}).get("embedded_closed", False):
        row["status"] = "exact_embedding_rejected"
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--split", required=True)
    args = parser.parse_args()
    CertifiedCutEngine.prepared = args.prepared
    controller.RemoteQuality = CertifiedCutEngine
    controller.mesh_valid = input_valid
    controller.VALID_SOURCE_BITS = (1, 2, 3)
    # 新入口显式继承已验证的共同来源表示，避免回退槽位阻断不依赖来源标签的算子。
    controller.clean_provenance = lambda mesh, bits: clean_provenance(mesh, bits, allow_shared=True)
    controller.source_region = lambda mesh, bits: source_region(mesh, bits, allow_shared=True)
    controller.verify_labels = lambda *values: verify_labels(*values, allow_shared=True)
    first.mesh_valid = mesh_valid_exact_contacts
    controller.audit_candidate = audit
    controller.main()
