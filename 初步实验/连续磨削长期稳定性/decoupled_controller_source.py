"""生成材料/显示分版本的A/C控制器，原入口和历史实验不修改。"""
from pathlib import Path
from preserved_controller_source import replace_once


def build_decoupled_controller(source):
    source = 'from decoupled_material_gate import audit_material\n'+source
    source = replace_once(source, '    args = parser.parse_args()',
        '    parser.add_argument("--local-checker", type=Path, required=True)\n'
        '    parser.add_argument("--reference-batch", type=Path)\n'
        '    args = parser.parse_args()')
    source = replace_once(source, '    parser.add_argument("--host", default="connect.weste.seetacloud.com")',
        '    parser.add_argument("--host", required=True)')
    source = replace_once(source,
        '        ref_root = HERE / "实验结果/20260928_独立解析参照"\n'
        '        ref_manifest = json.loads((ref_root / "01-参照审计.json").read_text(encoding="utf-8"))\n'
        '        analytic_refs = {(r["route"], r["event"]): r for r in ref_manifest["rows"]}',
        '''        # 新输入显式指定解析参照，避免封存入口隐式读取历史目录。
        ref_root = args.reference_batch
        analytic_refs = {}
        analytic_manifest_sha = None
        if ref_root is not None:
            ref_path = ref_root / "01-参照审计.json"
            ref_manifest = json.loads(ref_path.read_text(encoding="utf-8"))
            analytic_refs = {(r["route"], r["event"]): r for r in ref_manifest["rows"]}
            analytic_manifest_sha = sha256(ref_path)''')
    source = replace_once(source, '        report = {"time_beijing": now(),',
        '        report = {"analytic_reference_manifest_sha256": analytic_manifest_sha, "branch_contracts": {"C0": "C材料提交独立于PaMO显示", "C1": "A维护网格父反馈"}, "time_beijing": now(),')
    source = replace_once(source, '            initial_valid, initial_metrics = mesh_valid(initial)',
        '''            initial_valid, initial_metrics = mesh_valid(initial)
            initial_metrics["historical_floating_valid"] = initial_valid
            initial_gate = audit_material(prepared / "inputs" / route["initial_mesh"],
                                          output / rid / "initial_material_gate", args.local_checker)
            initial_metrics["common_exact_mesh_gate"] = initial_gate
            initial_valid = initial_gate["passed"]''')
    source = replace_once(source, '            retained = []',
        '''            # 同一事件序号分别记录材料和显示；旧画面不能冒充当前材料。
            material_versions = {"C0": 0, "C1": 0}
            display_versions = {"C0": 0 if initial_valid else None, "C1": 0 if initial_valid else None}
            material_sha = {"C0": sha256(prepared / "inputs" / route["initial_mesh"]), "C1": sha256(prepared / "inputs" / route["initial_mesh"])}
            event_numbers = {value: index+1 for index, value in enumerate(route["cutting_prefix_ids"])}
            retained = []''')
    source = replace_once(source, '                    if not valid or m["fp32_zero_area_faces"] or row["cleanup_max_vertex_difference_mm"] > 1e-7:',
        '''                    material_gate = audit_material(clean_path, frame / (branch + "_material_gate"), args.local_checker)
                    row["common_exact_material_gate"] = material_gate
                    material_valid = material_gate["passed"] and row["cleanup_max_vertex_difference_mm"] <= 1e-7
                    if not material_valid:
                        row["status"], blocked[branch] = "material_input_invalid", True
                        continue
                    if branch == "C0":
                        # 先提交通过基本材料协议的Geogram网格；下面的PaMO拒绝只影响显示。
                        committed_remote = remote_frame + "/C0_committed_material.obj"
                        sftp.put(str(clean_path), committed_remote)
                        parents[branch] = committed_remote
                        material_versions[branch] = event_numbers[eid]
                        material_sha[branch] = sha256(clean_path)
                        row["material_commit"] = {"version": event_numbers[eid], "sha256": material_sha[branch],
                                                  "scope": "基本材料网格协议；累计几何证书未建立"}
                    if m["fp32_zero_area_faces"]:''')
    source = replace_once(source, '                        row["status"], blocked[branch] = "pamo_input_invalid", True',
        '                        row["status"] = "display_input_encoding_invalid"\n'
        '                        blocked[branch] = branch == "C1"')
    source = replace_once(source, '                        row["status"], blocked[branch] = "pamo_failed", True',
        '                        row["status"] = "pamo_failed"\n'
        '                        blocked[branch] = branch == "C1"')
    source = replace_once(source, '                    valid, m = mesh_valid(candidate)',
        '''                    valid, m = mesh_valid(candidate)
                    m["historical_floating_valid"] = valid
                    output_gate = audit_material(candidate_path, frame / (branch + "_output_gate"), args.local_checker)
                    m["common_exact_output_gate"] = output_gate
                    valid = output_gate["passed"]''')
    source = replace_once(source, '                        parents[branch] = clean_remote if branch == "C0" else p_remote',
        '''                        display_versions[branch] = event_numbers[eid]
                        if branch == "C1":
                            # A沿用接受的维护网格，C材料父网格已经在GPU维护前独立提交。
                            parents[branch] = p_remote
                            material_versions[branch] = event_numbers[eid]
                            material_sha[branch] = sha256(candidate_path)''')
    source = replace_once(source, '                    else:\n                        blocked[branch] = True\n                    print(rid, eid, branch, row["status"], flush=True)',
        '                    else:\n                        blocked[branch] = branch == "C1"\n'
        '                    print(rid, eid, branch, row["status"], flush=True)')
    source = replace_once(source, '                    if reuse:\n                        row.update',
        '''                    if reuse:
                        # 材料没有新增变化时仅推进事件版本；旧显示与材料摘要不对应则保留年龄。
                        previous_material_version = material_versions[branch]
                        material_versions[branch] = event_numbers[eid]
                        if display_versions[branch] == previous_material_version:
                            display_versions[branch] = event_numbers[eid]
                        row.update''')
    start = source.index('                for branch in ("C0", "C1"):\n')
    end = source.index('                if not reuse:\n', start)
    block = source[start:end]
    first, body = block.split('\n', 1)
    # finally覆盖GPU失败、编码拒绝和受阻分支的continue，保证完整版本/年龄入账。
    body = '\n'.join('    '+line if line else '' for line in body.split('\n'))
    final = '''                    finally:
                        row["material_version_after"] = material_versions[branch]
                        row["display_version_after"] = display_versions[branch]
                        row["material_sha256_after"] = material_sha[branch]
                        row["display_age_events"] = None if display_versions[branch] is None else event_numbers[eid]-display_versions[branch]
                        row["material_age_events"] = event_numbers[eid]-material_versions[branch]
                        row["material_parent_remote_after"] = parents[branch]
                        save(record, report)
'''
    source = source[:start]+first+'\n                    try:\n'+body+final+source[end:]
    return source
