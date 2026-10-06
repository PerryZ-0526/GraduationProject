"""为新固定几何版本生成独立控制器，旧状态机与实验文件不改写。"""


def replace_once(source,old,new):
    if source.count(old) != 1:
        raise ValueError("控制器冻结结构与预期不一致："+old)
    return source.replace(old,new)


def build_controller(source):
    source = "from preserved_feedback_gate import check_preserved_mesh, clean_for_backend, backend_methods\n"+source
    changes = (
        ("valid, checks = mesh_valid(initial)", "valid, checks = check_preserved_mesh(engine, args.output/'full_geometry_checks', initial, 'initial_'+rid)"),
        ("valid_ref, metrics = mesh_valid(mesh)", "valid_ref, metrics = check_preserved_mesh(engine, folder/'full_geometry_checks', mesh, 'reference')"),
        ("source, bits, cleanup = clean_provenance(source, bits)", "source, bits, cleanup = clean_for_backend(source, bits, branch)"),
        ("input_valid, input_metrics = mesh_valid(source)", "input_valid, input_metrics = check_preserved_mesh(engine, inputs/'full_geometry_checks', source, 'source')"),
        ('if not input_valid or input_metrics["fp32_zero_area_faces"]:', 'if not input_valid or (branch == "full" and input_metrics["fp32_zero_area_faces"]):'),
        ('methods = ("full",) if branch == "full" or not labels_valid else ("boolean", "expanded", "full")',
         'methods = backend_methods(branch, labels_valid)'),
        ('"fallback": "expanded_once_then_original_full"', '"fallback": "expanded_once_without_original_fallback_for_fixed_geometry_candidate"'),
    )
    for old,new in changes:
        source = replace_once(source,old,new)
    return source


def build_reference(source):
    source = replace_once(source,"from fragment_pipeline import repair_input", "from preserved_feedback_gate import repair_reference_input")
    source = replace_once(source,"from exact_alarm_contact import mesh_valid_exact_contacts", "from preserved_feedback_gate import local_fp64_valid as mesh_valid_exact_contacts")
    return replace_once(source,"repair_input(clean,labels,audit=mesh_valid_exact_contacts)","repair_reference_input(clean,labels)")
