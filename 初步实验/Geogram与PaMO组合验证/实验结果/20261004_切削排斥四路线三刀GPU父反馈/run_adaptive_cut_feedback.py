"""独立累计参照引导的自适应整面排斥，保留原版配对父反馈及一次GPU预算。"""

import argparse
import json
from pathlib import Path
import re
import shutil
from time import perf_counter

import trimesh

import run_constrained_feedback as controller
import run_cut_exclusion_feedback as first
from run_cut_exclusion_feedback import ExclusionEngine, audit_exclusion
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import save
from audit_followup_candidate import sha256
from exact_alarm_contact import mesh_valid_exact_contacts
from study_cut_exclusion import input_valid
from adaptive_cut_exclusion import adaptive_exclusion
from locality_masks import save_obj_fp64


class AdaptiveCutEngine(ExclusionEngine):
    def setup(self):
        info = super().setup()
        names = ("adaptive_cut_exclusion.py", "run_adaptive_cut_feedback.py", "pilot_cut_exclusion.py",
                 "exact_alarm_contact.py", "study_cut_exclusion.py")
        for name in names:
            shutil.copyfile(HERE / name, self.output / name)
        info.update(adaptive_cut_code_sha256={name: sha256(HERE / name) for name in names},
                    mechanism="cumulative_reference_targets_trust_ball_face_exclusion_and_at_most_two_conforming_refinements",
                    input_policy="both_branches_positive_area_plus_exact_alarm_contact_diagnostic",
                    output_policy="unchanged_area_geometry_and_topology_with_same_exact_alarm_contact_review")
        return info

    def run(self, source, labels, tool, method, folder):
        match = re.fullmatch(r"(.+)_(e\d+)_(full|candidate)_(full|boolean|expanded)", Path(folder).name)
        if match is None:
            raise ValueError("前缀身份无法识别")
        rid, event, branch, _ = match.groups()
        if branch == "candidate" and method != "boolean":
            return {"method": method, "execution": {"returncode": "not_registered_candidate_attempt"},
                    "status": "not_run_budget_excluded"}
        row = RemoteQuality.run(self, source, labels, tool, "full", folder)
        row.update(method=method, actual_gpu_method="original_full_PaMO")
        if row["execution"]["returncode"] or branch == "full":
            return row
        folder = Path(folder)
        reference_path = self.output / f"{rid}_{event}_reference/reference.obj"
        if not reference_path.exists():
            row["cut_exclusion"] = {"accepted": False, "reason": "independent_reference_missing"}
            return row
        reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
        valid, checks = input_valid(reference)
        if not valid:
            row["cut_exclusion"] = {"accepted": False, "reason": "independent_reference_invalid", "checks": checks}
            return row
        raw = folder / "candidate.obj"
        shutil.copyfile(raw, folder / "raw_full_candidate.obj")
        route = self.routes[rid]
        current = route["cutting_prefix_ids"].index(event)
        events = set(route["cutting_prefix_ids"][:current + 1])
        paths = [self.prepared / "inputs" / entry["mesh"] for entry in route["prefix_tools"] if entry["event_id"] in events]
        tools = [trimesh.load(path, force="mesh", process=False) for path in paths]
        start = perf_counter()
        candidate, details = adaptive_exclusion(trimesh.load(raw, force="mesh", process=False), tools, reference)
        details.update(correction_cpu_ms=(perf_counter() - start) * 1000, cumulative_reference_sha256=sha256(reference_path),
                       cumulative_tool_sha256=[sha256(path) for path in paths])
        row.update(cut_exclusion=details, raw_full_output_sha256=sha256(raw))
        save_obj_fp64(candidate, raw)
        row["output_sha256"] = sha256(raw)
        save(folder / "03-自适应累计排斥记录.json", details)
        return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--split", required=True)
    args = parser.parse_args()
    AdaptiveCutEngine.prepared = args.prepared
    controller.RemoteQuality = AdaptiveCutEngine
    controller.mesh_valid = input_valid
    first.mesh_valid = mesh_valid_exact_contacts
    controller.audit_candidate = audit_exclusion
    controller.main()
