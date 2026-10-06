"""统一从已审计精确布尔源运行作者阶段二三及累计排斥真实反馈开发。"""

import argparse
import json
from pathlib import Path
import shutil

import trimesh
import numpy as np
from strict_no_change_reuse import try_strict_no_change_reuse
from exact_oriented_surface_identity import exact_oriented_surface_identity

from run_reference_cut_feedback import audit_full_embedding
from run_late_reverse_feedback import LateReverseEngine as ReferenceCutEngine
import run_reference_cut_feedback as reference
from distribution_observation_engine import DistributionObservationEngine, audit_distribution_observation
import distribution_observation_engine as observation
from quality_ranked_exclusion import quality_ranked_exclusion
from raw_seed_after_reference_failure import raw_seed_after_reference_failure
observation.distribution_ranked_exclusion = raw_seed_after_reference_failure
from geometry_error_distribution import geometry_error_distribution
from run_constrained_feedback import PROVENANCE, global_geometry
from run_geometry_study import execute, retrieve, save, now
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from locality_masks import save_obj_fp64
from locality_cleanup import clean_provenance
from locality_diagnostic import source_region, verify_labels
from native_fp32_fragment_guard import repair_input_native_fp32 as repair_input
from study_cut_exclusion import input_valid
from physical_source_before_encoding_audit import audit_physical_source
from guarded_encoded_orientation_preparation import prepare_encoded_orientation_source as prepare_encoded_source
from run_canonical_stepwise_feedback import canonical_repair as repair_input
from exact_duplicate_cleanup_fallback import clean_with_exact_duplicate_fallback as clean_provenance


from audited_encoding_origin import select_audited_origin
from inherit_encoding_origin_prefix import inherit_origin_prefix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--reference-batch", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--route", help="多路线资产中明确指定本次完整开发路线")
    parser.add_argument("--build-record", type=Path, required=True)
    parser.add_argument("--offset-factor", type=float, choices=(0.0, 0.45, 0.9), required=True)
    parser.add_argument("--inherited-prefix", type=Path, required=True, help="已独立复审的显式兼容前缀，不重跑既有GPU")
    args = parser.parse_args()
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text("utf8"))
    previous = json.loads((args.reference_batch / "01-独立累计参照绑定.json").read_text("utf8"))
    if previous["manifest_sha256"] != sha256(manifest_path):
        raise ValueError("本入口要求相同初态与工具的独立累计参照")
    # 多骨开发每次显式选择一条完整路线，结果仍保留该路线所有计划事件。
    routes = [r for r in manifest["routes"] if args.route is None or r["id"] == args.route]
    if len(routes) != 1:
        raise ValueError("必须唯一指定本次完整路线")
    route = routes[0]
    rid = route["id"]
    parent = args.prepared / "inputs" / route["initial_mesh"]
    if sha256(parent) != route["initial_mesh_sha256"]:
        raise ValueError("初态摘要不符")
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine = DistributionObservationEngine
    ReferenceCutEngine.prepared = args.prepared
    ReferenceCutEngine.side_validation = args.side_validation
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，误差分布观察路线先冻结",
              "文档概述": "已见开发继承三发布与两同源完整控制后继续，单列继承及新GPU，不称单版本从初态或最终质量结论",
              "索引目录": ["environment", "rows", "summary"], "status": "running", "rows": [],
              "manifest_sha256": sha256(manifest_path), "reference_batch_sha256": sha256(args.reference_batch / "01-独立累计参照绑定.json"),
              "snapshot_sha256": sha256(Path(__file__).with_name("01-执行源码冻结清单.json")),
              # 逐次翻边与折叠使用相同的实际来源提交守卫。
              "source_flip_candidate_guard": "actual_parent_and_tool_before_each_commit_same_1e_8_mm",
              "protocol": {"max_blocks": 1 << 26, "input_guard": "FP64_physical_source_then_actual_initial_centered_and_canonical_SDF_gates",
                           "source_collapse_candidate_guard": "actual_parent_and_tool_before_each_commit_same_1e_8_mm",
                           "input_unresolved_alarms_full_embedding_check": True,
                           "full_embedding_gate": True, "geometry_reference_distance_mm": .1, "fixed_geometry_acceptance_threshold": None, "publication_role": "geometry_observation_not_final_quality_acceptance", "max_refinement_levels": 4,
                           "GPU_calls_per_changed_event": 1, "strict_no_change_GPU_calls": 0, "fallback": "no_original_method_fallback", "role": "promoted_seven_family_evaluation_to_encoding_development"},
              "selected_route": rid}
    record = args.output / "01-统一配置完整父反馈记录.json"
    try:
        report["environment"] = engine.setup()
        report["environment"]["actual_parameters"]["ranking"] = "min_low_angle_fraction_then_worst_P95"
        report["protocol"].update(ranking="min_low_angle_fraction_then_worst_P95",
            quality_ranked_source_sha256=sha256(Path(__file__).with_name("quality_ranked_exclusion.py")))
        report["environment"]["actual_parameters"].update(extra_local_coverage_rounds_budget=2,
            local_coverage_trigger_mm=.1, projection_step_fractions=[1., .5, .25], maximum_coverage_proposals=6, step_applied_before_orientation_check=True, coverage_relocation="new_midpoints_and_forward_out_of_budget_old_vertices_in_seed")
        report["environment"]["native_FP32_guard_sha256"] = sha256(Path(__file__).with_name("native_fp32_fragment_guard.py"))
        report["environment"]["actual_parameters"]["native_FP32_fragment_arithmetic"] = True
        report["environment"]["local_coverage_sha256"] = sha256(Path(__file__).with_name("stepwise_coverage_exclusion.py"))
        save(args.output / "03-实际分支协议冻结.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，本批几何分布观察协议先于输出",
            "文档概述": "原有限提案与合法性门槛保持，几何误差只统计并排序，不设固定达标率",
            "索引目录": ["environment"], "environment": report["environment"]})
        # 隔离入口接FP64三角SDF扩展，原简化与投影核不修改。
        original_worker = Path(__file__).with_name("run_constrained_worker.py")
        engine.sftp.put(str(original_worker), engine.remote + "/original_run_constrained_worker.py")
        launcher = args.output / "capacity_launcher.py"
        launcher.write_text("\n".join([
            "import hashlib,inspect,json", "from pamo_safe_project import Stage3Config",
            "digest=hashlib.sha256(open(inspect.getfile(Stage3Config),'rb').read()).hexdigest()",
            "assert digest=='df1eb24db57394c32e31f6d67a58cd7ef6c25febc11aff39c5e9503ee82d6390'",
            "original=Stage3Config.__init__", "def larger(self,*args,**kwargs):",
            "    original(self,*args,**kwargs)", "    assert self.max_blocks == 1<<25",
            "    self.max_blocks=1<<26",
            "    print(json.dumps({'original_config_sha256':digest,'max_blocks':self.max_blocks}),flush=True)",
            "Stage3Config.__init__=larger", "import original_run_constrained_worker as worker", "worker.main()"]), encoding="utf8")
        # 隔离排序扩展先于作者包加载，完整阶段结构保持，只改变第一阶段偏移幅度。
        build = json.loads(args.build_record.read_text("utf8"))
        if build["status"] != "completed":
            raise ValueError("排序构建未完成")
        extension = next(x for x in build["builds"] if x["variant"] == "sorted")
        # 记录实际内存修订模块和构建绑定，避免将兼容选择键误称旧排序版本。
        report["environment"].update(GPU_simplifier_module=extension["module"], GPU_simplifier_sha256=extension["extension_sha256"], GPU_build_record_sha256=sha256(args.build_record))
        if execute(engine.client, ["sha256sum", extension["extension"]])["stdout"].split()[0] != extension["extension_sha256"]:
            raise ValueError("实际排序扩展摘要已变化")
        header = "\n".join([
            "# 只在隔离进程载入已冻结邻接排序扩展，不改作者安装。",
            "import torch,sys,hashlib,importlib.util",
            "extension_path=" + repr(extension["extension"]),
            "assert hashlib.sha256(open(extension_path,'rb').read()).hexdigest()==" + repr(extension["extension_sha256"]),
            "spec=importlib.util.spec_from_file_location(" + repr(extension["module"]) + ",extension_path)",
            "extension=importlib.util.module_from_spec(spec)",
            "spec.loader.exec_module(extension)", "sys.modules['pamo._C']=extension", ""])
        # 轻量偏移适配没有逐轮网格与张量观测，避免将额外诊断同步混入连续流程。
        bias_source = Path(__file__).with_name("sdf_bias_remesh.py")
        engine.sftp.put(str(bias_source), engine.remote + "/sdf_bias_remesh.py")
        if execute(engine.client, ["sha256sum", engine.remote + "/sdf_bias_remesh.py"])["stdout"].split()[0] != sha256(bias_source):
            raise ValueError("实际偏移适配源码摘要不符")
        header += "from sdf_bias_remesh import install_bias\ninstall_bias(" + repr(args.offset_factor) + ")\n"
        report["protocol"].update(stage1_SDF_offset_factor=args.offset_factor, stage1_bias_sha256=sha256(bias_source), origin_rule="fixed_FP64_triangle_mean_before_orientation_fragment_preparation", normalization="FP64_normalization_and_FP64_SDF_triangle_input", physical_fragment_preparation="encoded_orientation_trigger_existing_operations_then_actual_working_source_gates")
        report["environment"]["actual_parameters"].update(stage1="author_disabled_option", stage1_SDF_offset_factor=None, actual_stage_calls={"stage1": 0, "stage2": 1, "stage3": 1})
        # 冻结公共入口，每刀再绑定当前工具原点和各自工作源目录。
        # 新表示模块必须与调用模块一并上传，并逐个核对远端摘要。
        for name in ("no_secondary_center.py", "tool_origin_encoding.py", "normalized_sdf_chain.py", "normalized_working_source_gate.py", "fp64_sdf_normalization.py", "minimum_sdf_resolution.py", "simplification_budget_ratio.py", "binary_stage3_representation.py", "contact_stage3_conditioning.py", "contact_conditioning_geometry.py", "encoding_bound_small_face_endpoint.py", "stage3_encoding_bound_area_control.py"):
            path = Path(__file__).with_name(name)
            engine.sftp.put(str(path), engine.remote + "/" + name)
            if execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0] != sha256(path):
                raise ValueError("实际工作源门控模块摘要不同")
        launcher.write_text(header + launcher.read_text("utf8"), "utf8")
        # 报告绑定分辨率分解修复版私有扩展，不混用旧扩展结论。
        report["SDF_extension_sha256"] = "daed27cf1037c75ab527c6df74a56400ac9cf91c63c184ebd3260d23fec5401e"
        report["protocol"].update(SDF_compile_flags="O3_no_fast_math_sm89", minimum_SDF_resolution=640, simplification_target_ratio="min_four_input_faces_and_four_independent_reference_faces", raw_seed_extra_proposals_budget=1, postprocessing_trigger="no_legal_candidate_in_original_fixed_budget", reuse_support="tool_face_normals_then_failed_triangle_own_normals_exact_tool_containment", resolution_policy="max_author_target_face_rule_and_640")
        # 自动面分离版本独立报告新增提案、算法半径和轮数，不改历史方法证据。
        report["protocol"].update(automatic_pair_guard_sha256=sha256(Path(__file__).with_name("automatic_pair_separation.py")),
                                  automatic_pair_guard_budget_mm=.3, automatic_pair_added_rounds_budget=3,
                                  pair_detection="full_exact_stored_candidate_then_original_face_separator",
                                  preserved_original_successes=True)
        # 统一阶段开关候选明确列出实际GPU阶段，不能称原三阶段完整调用。
        report["protocol"].update(use_stage1=False, use_stage3=True, configured_stage_switches_per_changed_event={"stage1": 0, "stage2": 1, "stage3": 1},
            active_SDF_resolution=None, exact_source_stage23_sha256=sha256(Path(__file__).with_name("minimum_sdf_resolution.py")),
            stage1_policy="uniform_author_disabled_option_not_shape_specific_fallback")
        # 原预算邻面位置和排斥后面积修复分别记录，输入、最终门槛均不放宽。
        report["protocol"].update(incident_plane_collapse_sha256=sha256(Path(__file__).with_name("incident_plane_collapse.py")),
            incident_plane_tolerance_mm=1e-8, physical_small_area_trigger_mm2=1e-12,
            post_exclusion_area_repair_sha256=sha256(Path(__file__).with_name("post_exclusion_area_repair.py")),
            source_repair="endpoints_then_edge_internal_then_same_plane_budget_local_3D",
            post_area_guard="all_cumulative_tool_face_certificates_before_each_collapse")
        # 两处焊接策略均独立绑定，所有后续来源、编码和累计排斥审查继续执行。
        report["protocol"].update(cleanup_duplicate_fallback="exact_coordinate_weld_no_rounding_no_face_deletion",
            exact_cleanup_sha256=sha256(Path(__file__).with_name("exact_duplicate_cleanup_fallback.py")),
            stage2_default_tolerance_weld=False, stage2_constructor="trimesh_process_false",
            fp64_normalization_sha256=sha256(Path(__file__).with_name("fp64_sdf_normalization.py")))
        # 该版本按输入资格选择阶段，不是统一关闭阶段一，也不宣称每帧完整三阶段。
        report["protocol"].update(use_stage1="selected_from_residual_positive_small_source",
            configured_stage_switches_per_changed_event="stage1_conditional_stage2_and_stage3_always",
            active_SDF_resolution="640_only_when_original_stage1_enabled",
            stage1_policy="positive_embedded_source_with_unresolved_physical_small_faces_then_original_reconstruction",
            stage23_policy="prepared_source_meets_final_area_floor",
            final_output_area_floor_mm2=1e-12)
        # 本版只改实际碰撞表示，分辨率与全部源及输出验收保持原冻结值。
        # 第三阶段保留工具原点，以二次幂表示并换算物理参数，不宣称数值等价。
        # 原导数保持，新增预检计数与动态有限预算，不把GPU预检当完整发布。
        report["protocol"].update(collision_conditioning="original_nonfinite_EE_contact_shortest_edge_endpoint", collision_conditioning_collapse_budget="initial_bad_contact_count", collision_conditioning_plane_budget_mm=1e-8, collision_conditioning_no_gradient_replacement=True, collision_conditioning_module_sha256=sha256(Path(__file__).with_name("contact_stage3_conditioning.py")), collision_conditioning_geometry_sha256=sha256(Path(__file__).with_name("contact_conditioning_geometry.py")))
        report["protocol"].update(stage3_representation="power_of_two_floor_no_extra_translation", stage3_physical_length_preserved=True, stage3_energy_dimension_rescaled=True, stage3_finite_precision_equivalence_claim=False, stage3_module_sha256=sha256(Path(__file__).with_name("binary_stage3_representation.py")))
        # 在GPU简化回退处执行实际FP32全量EPECK检查，完整保留累计条目。
        report["protocol"].update(simplifier_self_intersection="CPU_EPECK_on_all_actual_FP32_faces_each_undo_check", simplifier_invalid_state="all_original_face_slots_for_current_collapse_undo", simplifier_undo_entries="full_cumulative_storage_initialized_pending_tail", simplification_metric="unchanged_physical_coordinates", simplifier_skinny_cost="unchanged_original_expression", target_face_budget_is_not_guaranteed=True)
        report["protocol"].update(secondary_FP32_centering=False, source_encoding="single_tool_origin_then_zero_author_mean", full_working_source_and_final_gates_preserved=True)
        # 同一预算下，碰撞面联合保持相对分离；末输出仍作完整精确审核。
        report["protocol"].update(pair_projection="joint_vertices_with_exact_relative_pair_certificates", shared_vertex_anchor="actual_saved_shared_vertex", disjoint_plane_offset="free_relative_order_with_frozen_original_normal")
        # 本版统一关闭重建，完整源门控、原求解与原排斥回退逻辑继续执行。
        report["protocol"].update(use_stage1=False, active_SDF_resolution=None,
            configured_stage_switches_per_changed_event={"stage1": 0, "stage2": 1, "stage3": 1},
            stage1_policy="preserve_actual_boolean_source_without_SDF_reconstruction",
            area_conditioning="strictly_decreasing_small_face_count_exact_endpoint_collapses",
            area_edge_and_plane_budget="two_actual_source_encoding_errors_each_event",
            area_collapse_count_budget="initial_small_face_count",
            stage23_policy="exact_positive_source_then_actual_candidate_area_conditioning_before_original_solver",
            area_conditioning_final_floor_unchanged=True,
            correction_protocol="unchanged_raw_seed_after_reference_failure",
            area_control_sha256=sha256(Path(__file__).with_name("stage3_encoding_bound_area_control.py")))
        # 默认编码合法立即保留，仅失效时按交叠面几何生成表示原点候选。
        report["protocol"].update(origin_rule="default_then_source_mean_bbox_intersection_faces_and_pair_centers_first_embedded",
            source_encoding="single_selected_origin_then_zero_author_mean",
            source_origin_selection_sha256=sha256(Path(__file__).with_name("geometry_selected_encoding_origin.py")),
            actual_GPU_working_source_gates_preserved=True,
            continuation="three_prior_publications_and_two_verified_same_source_controls_then_original_remaining_events",
            single_version_from_initial_run=False)
        # 只对原导数异常触发的最短边试原端点，局部平面预算和映射界来自实际物理边长。
        report["protocol"].update(collision_conditioning="original_nonfinite_EE_contact_shortest_edge_endpoint_local_mapping_bound",
            collision_conditioning_plane_budget_mm=None,
            collision_conditioning_plane_budget_rule="actual_shortest_bad_contact_edge_length_mm",
            collision_conditioning_geometric_bound="same_barycentric_endpoint_triangle_mapping_relative_to_actual_candidate",
            collision_conditioning_collapse_budget="initial_bad_contact_count",
            collision_conditioning_no_gradient_replacement=True)
        report["sorted_extension"] = extension
        report["protocol"].update(simplification="isolated_author_source_with_sorted_vertex_triangle_adjacency",
            original_simplification_binary=False, extra_reverse_passes_budget=1,
            reverse_trigger_mm=.1, stage_observation_enabled=False, extra_local_coverage_rounds_budget=2,
            coverage_relocation="new_midpoints_and_forward_out_of_budget_old_vertices_in_seed", bidirectional_marking=True, projection_step_fractions=[1., .5, .25], maximum_coverage_proposals=6, step_applied_before_orientation_check=True, native_FP32_fragment_arithmetic=True)
        engine.sftp.put(str(launcher), engine.remote + "/run_constrained_worker.py")
        actual = execute(engine.client, ["sha256sum", engine.remote + "/run_constrained_worker.py"])["stdout"].split()[0]
        if actual != sha256(launcher):
            raise ValueError("实际容量入口摘要不符")
        report["capacity_entry"] = {"actual_remote_sha256": actual, "original_worker_sha256": sha256(original_worker)}
        save(record, report)
        # 继承资格、保存复审、数值模块和真实父链均通过后，才采用已验证第五刀状态。
        parent = inherit_origin_prefix(args, report, route)
        inherited_events = {r["event"] for r in report["rows"]}
        save(record, report)
        for event in route["cutting_prefix_ids"]:
            if event in inherited_events:
                continue
            tool_info = next(t for t in route["prefix_tools"] if t["event_id"] == event)
            tool = args.prepared / "inputs" / tool_info["mesh"]
            if sha256(tool) != tool_info["sha256"]:
                raise ValueError("冻结工具摘要不符")
            folder = args.output / f"{rid}_{event}_candidate_input"
            folder.mkdir()
            row = {"route": rid, "event": event, "parent_sha256": sha256(parent), "tool_sha256": sha256(tool), "status": "pending"}
            report["rows"].append(row)
            save(record, report)
            # 无合法独立参照的事件单独拒绝，不用原始失败参照继续GPU或抛出未记账异常。
            reference_binding = next(item for item in previous["rows"] if item["route"] == rid and item["event"] == event)
            if reference_binding["status"] != "reference_valid" or reference_binding.get("reference_sha256") is None:
                row["status"] = "independent_reference_rejected"
                row["independent_reference_status"] = reference_binding["status"]
                break
            for path, name in ((parent, "parent.obj"), (tool, "tool.obj")):
                engine.sftp.put(str(path), engine.remote + "/" + name)
                if execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0] != sha256(path):
                    raise ValueError("实际布尔父输入或工具摘要不符")
            run = execute(engine.client, [PROVENANCE, engine.remote + "/parent.obj", engine.remote + "/tool.obj",
                engine.remote + "/source.obj", engine.remote + "/labels.json", "--no-simplify"], engine.remote + "/geogram.log")
            row["geogram_execution"] = run
            if run["returncode"]:
                row["status"] = "boolean_rejected"
                break
            for name in ("source.obj", "labels.json"):
                retrieve(engine.client, engine.sftp, engine.remote + "/" + name, folder / name)
            retrieve(engine.client, engine.sftp, engine.remote + "/geogram.log", folder / "geogram.log")
            source = trimesh.load(folder / "source.obj", force="mesh", process=False)
            bits = json.loads((folder / "labels.json").read_text("utf8"))["operand_bits"]
            # 预期输入清理拒绝正常记账，保留原事件及后续阻断，不遗留假运行状态。
            try:
                source, bits, row["cleanup"] = clean_provenance(source, bits, allow_shared=True)
            except ValueError as error:
                row.update(status="input_cleanup_rejected", cleanup_error=str(error))
                save(record, report)
                break
            valid, row["before_input_metrics"] = input_valid(source)
            # 物理FP64源统一完整审查；实际编码的FP32合法性由本刀GPU工作源门控负责。
            check_input = lambda mesh: audit_physical_source(engine, folder, mesh, row)
            valid, row["before_full_embedding_metrics"] = check_input(source)
            if not valid:
                source, bits, row["input_repair"] = repair_input(source, bits, audit=check_input, allow_shared=True, allow_small_incident=True)
            # 折叠提交前使用本刀实际父与原工具复核，失败候选不消耗已接受折叠预算。
            parent_geometry = trimesh.load(parent, force="mesh", process=False)
            tool_geometry = trimesh.load(tool, force="mesh", process=False)
            def provenance_guard(trial, trial_bits):
                _, _, trial_seam = source_region(trial, trial_bits, allow_shared=True)
                return verify_labels(trial, trial_bits, parent_geometry, tool_geometry, trial_seam,
                                     allow_shared=True)["passed_1e_8_mm_numerical_check"]
            source, bits, row["encoded_fragment_preparation"] = prepare_encoded_source(
                source, bits, audit=check_input, candidate_guard=provenance_guard)
            valid, row["after_input_metrics"] = check_input(source)
            # 阶段二三资格与原阶段一恢复资格分别决定，不能以输入正面积替代最终输出下限。
            # 保留实际布尔曲面，低面积候选在原求解前按本刀实测编码误差处理。
            row["prepared_stage1_recommendation"] = row["encoded_fragment_preparation"]["selected_use_stage1"]
            row["selected_use_stage1"] = False
            if not (row["encoded_fragment_preparation"]["physical_candidate_ready_for_actual_encoding_gate"] or
                    row["encoded_fragment_preparation"]["physical_candidate_ready_for_full_stage1_encoding_gate"]):
                valid = False
            source_path, labels_path = folder / "clean_source.obj", folder / "clean_labels.json"
            save_obj_fp64(source, source_path)
            save(labels_path, {"operand_bits": bits.tolist()})
            if not valid:
                row["status"] = "maintenance_input_rejected"
                break
            _, _, seam = source_region(source, bits, allow_shared=True)
            row["provenance"] = verify_labels(source, bits, trimesh.load(parent, force="mesh", process=False),
                trimesh.load(tool, force="mesh", process=False), seam, allow_shared=True)
            if not row["provenance"]["passed_1e_8_mm_numerical_check"]:
                row["status"] = "provenance_rejected"
                break
            remote = engine.remote + "/input_for_embedding.obj"
            engine.sftp.put(str(source_path), remote)
            run = execute(engine.client, [CHECKER, remote])
            row["input_exact_embedding"] = json.loads(run["stdout"]) if not run["returncode"] else {"execution": run}
            if not row["input_exact_embedding"].get("embedded_closed"):
                row["status"] = "input_exact_embedding_rejected"
                break
            # 独立累计参照仅由相同初态和工具生成，与本批实际反馈父网格分离。
            reference_folder = args.output / f"{rid}_{event}_reference"
            shutil.copytree(args.reference_batch / reference_folder.name, reference_folder)
            reference_path = reference_folder / "validated_reference.obj"
            if not reference_path.exists():
                reference_path = reference_folder / "reference.obj"
            # 复制后核对独立参照绑定，不把候选父反馈生成的对象冒充累计真值。
            binding = next(item for item in previous["rows"] if item["route"] == rid and item["event"] == event)
            if reference_path.exists() and sha256(reference_path) != binding["reference_sha256"]:
                raise ValueError("复制后的独立累计参照摘要不匹配")
            # 独立参照缺失时在GPU前停止，保留本帧及后续阻断状态。
            if not reference_path.exists():
                row["status"] = "independent_reference_missing"
                break
            destination = args.output / f"{rid}_{event}_candidate_boolean"
            save(record, report)
            raw_source = trimesh.load(folder / "source.obj", force="mesh", process=False)
            raw_bits = json.loads((folder / "labels.json").read_text("utf8"))["operand_bits"]
            row["raw_boolean_identity"] = exact_oriented_surface_identity(
                trimesh.load(parent, force="mesh", process=False), raw_source, raw_bits)
            prefix = set(route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index(event) + 1])
            cumulative_tools = [args.prepared / "inputs" / t["mesh"] for t in route["prefix_tools"] if t["event_id"] in prefix]
            # 原始布尔输出和准备后源均严格相同才允许复用，不能由清理掩盖变化。
            attempt = try_strict_no_change_reuse(engine, parent, source_path, labels_path,
                cumulative_tools, destination) if row["raw_boolean_identity"]["same"] else None
            if attempt is not None:
                row["execution_role"] = "strict_no_change_reuse"
                print(event, attempt["status"], flush=True)
            else:
                row["execution_role"] = "source_encoding_selection_before_GPU"
                print(event, "encoding_origin_selection_started", flush=True)
                # 优先保留原准备原点，只有编码精确检查失败才选择同源几何候选；物理源不动。
                origin = row["encoded_fragment_preparation"]["fixed_operation_origin_mm"]
                selected = select_audited_origin(engine, source, origin, args.output / (event + "_encoding_origin_selection"))
                row["encoding_origin_selection"] = selected
                if selected["status"] != "selected":
                    row["status"] = "source_encoding_origin_rejected"
                    save(record, report)
                    break
                origin = selected["selection"]["origin_mm"]
                row["execution_role"] = "configured_adaptive_stage_GPU_and_correction"
                event_launcher = args.output / (event + "_working_source_launcher.py")
                common = launcher.read_text("utf8")
                marker = "import original_run_constrained_worker as worker"
                install = "from tool_origin_encoding import install_tool_origin\ninstall_tool_origin(" + repr(origin) + ")\n"
                install += "from fp64_sdf_normalization import install_fp64_sdf_normalization\ninstall_fp64_sdf_normalization()\n"
                install += "from minimum_sdf_resolution import install_minimum_sdf_resolution\ninstall_minimum_sdf_resolution(640, use_stage1=" + repr(row["selected_use_stage1"]) + ")\n"
                install += "from simplification_budget_ratio import install_simplification_budget_ratio\ninstall_simplification_budget_ratio(4, " + repr(len(trimesh.load(reference_path, process=False).faces)) + ")\n"
                install += "from normalized_working_source_gate import install_working_source_gate\ninstall_working_source_gate(" + repr(engine.remote + "/" + event + "_working_sources") + ")\n"
                # 本刀在完整求导前审查实际Warp表示，换算长度和权重后执行原求解。
                install += "from binary_stage3_representation import install_binary_stage3_representation\ninstall_binary_stage3_representation(" + repr(engine.remote + "/" + event + "_stage3_working_sources") + ")\n"
                # 与工具原点入口使用同一公式测量当前源编码误差，不读取旧刀固定数值。
                local_values = np.asarray(source.vertices, np.float64) - np.asarray(origin, np.float64)
                encoding_error = float(np.linalg.norm(local_values.astype(np.float32).astype(np.float64) + np.asarray(origin, np.float64) - source.vertices, axis=1).max())
                row["area_control_source_encoding_error_mm"] = encoding_error
                install += "from stage3_encoding_bound_area_control import install_area_control\ninstall_area_control(" + repr(encoding_error) + ", " + repr(engine.remote + "/" + event + "_area_conditioning") + ")\n"
                if common.count(marker) != 1:
                    raise ValueError("公共入口的工作源门控安装点不唯一")
                event_launcher.write_text(common.replace(marker, install + marker), "utf8")
                engine.sftp.put(str(event_launcher), engine.remote + "/run_constrained_worker.py")
                if execute(engine.client, ["sha256sum", engine.remote + "/run_constrained_worker.py"])["stdout"].split()[0] != sha256(event_launcher):
                    raise ValueError("本刀实际工作源入口摘要错误")
                row.update(actual_launcher_sha256=sha256(event_launcher), origin_mm=origin)
                save(record, report)
                # 本刀原求解完成后，排斥及最终输出均按声明原点读取实际CUDA/Warp表示。
                import exact_embedding_gate as output_gate
                from runtime_output_representation import RuntimeOutputRepresentation
                output_gate.ACTUAL_OUTPUT_REPRESENTATION_GUARD = RuntimeOutputRepresentation(
                    engine, args.output / (event + "_output_representation"), origin, None,
                    engine.remote + "/" + event + "_stage3_working_sources/01-第三阶段实际表示与求解记录.json")
                attempt = engine.run(source_path, labels_path, tool, "boolean", destination)
                gate_folder = args.output / (event + "_working_sources")
                gate_folder.mkdir()
                for name in ("01-CUDA初始编码源.obj", "02-CUDA再中心化碰撞源.obj", "03-整理后归一化SDF源.obj", "04-完整求解前实际工作源门控.json"):
                    remote_gate = engine.remote + "/" + event + "_working_sources/" + name
                    try:
                        engine.sftp.stat(remote_gate)
                    except FileNotFoundError:
                        continue
                    retrieve(engine.client, engine.sftp, remote_gate, gate_folder / name)
                # 保存实际第三阶段输入和求解计数，失败输入也保留拒绝证据。
                stage3_folder = args.output / (event + "_stage3_working_sources")
                stage3_folder.mkdir()
                for name in ("候选实际Warp编码.obj", "源实际Warp编码.obj", "01-第三阶段实际表示与求解记录.json"):
                    remote_stage3 = engine.remote + "/" + event + "_stage3_working_sources/" + name
                    try:
                        engine.sftp.stat(remote_stage3)
                    except FileNotFoundError:
                        continue
                    retrieve(engine.client, engine.sftp, remote_stage3, stage3_folder / name)
                # 读取自动触发和几何折叠记录，保存实际初始与改善输入，不隐藏失败探针。
                condition_folder = stage3_folder / "collision_conditioning"
                condition_folder.mkdir()
                remote_condition = engine.remote + "/" + event + "_stage3_working_sources/collision_conditioning"
                try:
                    condition_names = engine.sftp.listdir(remote_condition)
                except FileNotFoundError:
                    condition_names = []
                for name in condition_names:
                    if name.endswith((".json", ".npz", ".obj")):
                        retrieve(engine.client, engine.sftp, remote_condition + "/" + name, condition_folder / name)
                condition_record = condition_folder / "01-原碰撞失稳自动局部几何记录.json"
                row["actual_collision_conditioning"] = json.loads(condition_record.read_text("utf8")) if condition_record.exists() else {"status": "unavailable_due_to_earlier_execution_failure"}
                # 面积处理提案与实际精确检查全部保存，失败也留原始记录。
                area_folder = args.output / (event + "_area_conditioning")
                area_folder.mkdir()
                remote_area = engine.remote + "/" + event + "_area_conditioning"
                try:
                    area_names = engine.sftp.listdir(remote_area)
                except FileNotFoundError:
                    area_names = []
                for name in area_names:
                    if name.endswith((".json", ".obj")):
                        retrieve(engine.client, engine.sftp, remote_area + "/" + name, area_folder / name)
                area_record = area_folder / "01-实际编码误差预算低面积处理.json"
                row["actual_area_conditioning"] = json.loads(area_record.read_text("utf8")) if area_record.exists() else {"status": "unavailable_due_to_earlier_execution_failure"}
                if not attempt["execution"]["returncode"] and row["actual_area_conditioning"]["status"] != "completed_area_conditioning":
                    raise ValueError("GPU成功但实际面积处理记录未通过")
                stage3_record = stage3_folder / "01-第三阶段实际表示与求解记录.json"
                row["actual_stage3_representation"] = json.loads(stage3_record.read_text("utf8")) if stage3_record.exists() else {"status": "unavailable_due_to_earlier_execution_failure"}
                if not attempt["execution"]["returncode"] and row["actual_collision_conditioning"]["status"] != "completed_conditioning":
                    raise ValueError("GPU成功但原碰撞几何处理记录没有完成")
                if not attempt["execution"]["returncode"] and row["actual_stage3_representation"]["status"] != "completed_original_solver":
                    raise ValueError("GPU成功但第三阶段实际表示或求解记录未通过")
                gate_record = gate_folder / "04-完整求解前实际工作源门控.json"
                row["actual_working_source_gate"] = json.loads(gate_record.read_text("utf8")) if gate_record.exists() else {"status": "unavailable_due_to_earlier_execution_failure"}
                if not attempt["execution"]["returncode"] and row["actual_working_source_gate"]["status"] != "passed_before_full_solver":
                    raise ValueError("完整GPU成功但实际工作源门控缺失或不通过")
                # 每刀均明确标记实际偏移变体，不能继承原版方法名称作为新实验结论。
                attempt.update(actual_gpu_method="isolated_CPU_exact_self_intersection_GPU_QEM_and_original_physical_solver", stage1="author_enabled_for_residual_positive_small_faces" if row["selected_use_stage1"] else "author_disabled_option", stage1_SDF_offset_factor=0.0 if row["selected_use_stage1"] else None, configured_stage_switches={"stage1": int(row["selected_use_stage1"]), "stage2": 1, "stage3": 1}, actual_diff_calls=row["actual_stage3_representation"].get("diff_calls", 0), actual_CCD_calls=row["actual_stage3_representation"].get("ccd_calls", 0))
                attempt = audit_distribution_observation(source_path, tool, labels_path, destination, attempt)
                output_gate.ACTUAL_OUTPUT_REPRESENTATION_GUARD = None
            row["attempt"] = attempt
            if attempt["status"] != "accepted_geometry_observation":
                row["status"] = "candidate_rejected"
                break
            candidate_path = destination / "candidate.obj"
            candidate = trimesh.load(candidate_path, force="mesh", process=False)
            reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
            row["cumulative_geometry"] = global_geometry(candidate, reference)
            # 当前先统计再定比例，不按最大探针拒绝；观察发布不等于最终几何质量结论。
            row["cumulative_distribution"] = geometry_error_distribution(candidate, reference)
            row["geometry_quality_decision"] = "statistics_only_pending_evaluation"
            row.update(status="published_geometry_observation", output_sha256=sha256(candidate_path), reference_sha256=sha256(reference_path))
            parent = candidate_path
            save(record, report)
            print(event, "published_geometry_observation", flush=True)
        # 每个原计划事件保留状态，不能只用成功事件作分母。
        for event in route["cutting_prefix_ids"]:
            if not any(r["event"] == event for r in report["rows"]):
                report["rows"].append({"route": rid, "event": event, "status": "blocked_by_previous_failure"})
        report.update(status="completed_with_recorded_outcomes", finished_beijing=now(),
            summary={"published": sum(r["status"] == "published_geometry_observation" for r in report["rows"]),
                     "configured_GPU_calls": sum(r.get("execution_role") == "configured_adaptive_stage_GPU_and_correction" for r in report["rows"]),
                     "strict_reuses": sum(r.get("execution_role") == "strict_no_change_reuse" and r["status"] == "published_geometry_observation" for r in report["rows"]),
                     "inherited_prior_publications": 3, "adopted_same_source_controls": 2,
                     "new_published": sum(r["status"] == "published_geometry_observation" and r.get("execution_role") not in ("inherited_prior_publication", "adopted_verified_same_source_control") for r in report["rows"]),
                     "single_version_from_initial_run": False,
                     "events": len(route["cutting_prefix_ids"]), "whole_route_complete": all(r["status"] == "published_geometry_observation" for r in report["rows"])})
        save(record, report)
        print(report["summary"], flush=True)
    finally:
        import exact_embedding_gate as output_gate
        output_gate.ACTUAL_OUTPUT_REPRESENTATION_GUARD = None
        engine.close()


if __name__ == "__main__":
    main()
