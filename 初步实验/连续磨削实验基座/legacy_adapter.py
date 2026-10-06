"""既有Geogram、PaMO和活动面候选的冻结适配器。"""
from functools import partial
from pathlib import Path
from time import perf_counter
import shutil


class LegacyQuality:
    """新质量处理器实现这三个方法即可复用材料更新和评价。"""
    def __init__(self, engine):
        from preserved_feedback_gate import backend_methods
        from run_active_patch_feedback import audit_active_candidate
        self.engine, self.choose, self.evaluate = engine, backend_methods, audit_active_candidate

    def methods(self, branch, labels_valid):
        return self.choose(branch, labels_valid)

    def run(self, source, labels, tool, method, folder):
        return self.engine.run(source, labels, tool, method, folder)

    def audit(self, source, labels, tool, folder, attempt):
        return self.evaluate(self.engine, source, tool, labels, folder, attempt)


class LegacyBackend:
    def __init__(self, snapshot, attempt_folder, port, quality_plugin=None):
        import trimesh
        from run_active_patch_feedback import ActiveReferenceEngine
        from run_preserved_geometry_feedback import load_snapshot
        self.snapshot, self.output = Path(snapshot), Path(attempt_folder)
        self.output.mkdir(parents=True, exist_ok=False)
        for name in ('preserved_reference.py', 'preserved_controller.py'):
            shutil.copyfile(self.snapshot / name, self.output / name)
        ActiveReferenceEngine.entry_path = self.snapshot / 'physical_feedback_entry.py'
        self.engine = ActiveReferenceEngine(self.output, port)
        self.reference = load_snapshot('base_frozen_reference', self.snapshot / 'preserved_reference.py')
        self.quality = LegacyQuality(self.engine)
        if quality_plugin:
            module = load_snapshot('base_quality_plugin', quality_plugin)
            self.quality = module.create_processor(self.engine)
            for name in ('methods', 'run', 'audit'):
                if not callable(getattr(self.quality, name, None)):
                    raise TypeError('质量处理器缺少接口：' + name)
        self.load_mesh = partial(trimesh.load, force='mesh', process=False)

    def setup(self, prior_remotes):
        from run_geometry_study import execute, GEO
        from run_constrained_feedback import PROVENANCE
        from event_store import atomic_json
        # 本机异常退出后先确认本批旧远端命令结束，其他任务不受影响。
        result = execute(self.engine.client, ['ps', '-eo', 'pid,args'])
        if result['returncode']:
            raise RuntimeError('不能核查原远端任务')
        for remote in prior_remotes:
            live = [line for line in result['stdout'].splitlines() if remote in line
                    and any(name in line for name in ('run_constrained_worker.py', 'geogram_boolean', 'geogram_provenance', 'g++'))]
            if live:
                raise RuntimeError('本批原远端工作仍活动，禁止重新执行：' + live[0])
        info = self.engine.setup()
        result = execute(self.engine.client, ['sha256sum', PROVENANCE])
        if result['returncode']:
            raise RuntimeError('来源布尔二进制不可用')
        info['provenance_binary_sha256'] = result['stdout'].split()[0]
        info['geogram_binary_sha256'] = execute(self.engine.client, ['sha256sum', GEO])['stdout'].split()[0]
        atomic_json(self.output / '01-实际环境与工作器.json', info)
        return info

    def validate(self, mesh, folder, name):
        from preserved_feedback_gate import check_preserved_mesh
        return check_preserved_mesh(self.engine, Path(folder), mesh, name)

    def reference_step(self, prepared, route, event, folder):
        mesh, record = self.reference.recover_reference(self.engine, prepared, route, event, '', folder, False)
        if mesh is not None:
            valid, metrics = self.validate(mesh, folder / 'full_geometry_checks', 'recovered_reference')
            record.update(accepted=valid, validated_metrics=metrics)
            if not valid:
                return None, record
        return mesh, record

    def run_branch(self, route, event, branch, parent, tool_path, initial, reference, folder):
        import json
        from event_store import digest, file_identity, atomic_json
        from locality_masks import save_obj_fp64
        from ordered_physical_cleanup import clean_for_backend
        from locality_diagnostic import source_region, verify_labels
        from run_constrained_feedback import global_geometry, PROVENANCE
        from geometry_preservation_audit import preservation
        from run_geometry_study import execute, retrieve
        started = perf_counter()
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=False)
        engine = self.engine
        row = {'route': route['id'], 'event': event, 'branch': branch,
               'parent_sha256': digest(parent), 'tool_sha256': digest(tool_path), 'timings_ms': {}}
        inputs = folder / 'input'
        inputs.mkdir()
        stem = folder.name
        parent_remote = engine.remote + '/' + stem + '_parent.obj'
        tool_remote = engine.remote + '/' + stem + '_tool.obj'
        source_remote = engine.remote + '/' + stem + '_source.obj'
        labels_remote = engine.remote + '/' + stem + '_labels.json'
        engine.sftp.put(str(parent), parent_remote)
        engine.sftp.put(str(tool_path), tool_remote)
        cutting = perf_counter()
        result = execute(engine.client, [PROVENANCE, parent_remote, tool_remote, source_remote, labels_remote,
                                        '--no-simplify'], source_remote + '.log', timeout=120)
        retrieve(engine.client, engine.sftp, source_remote + '.log', inputs / 'geogram.log')
        row['geogram_run'] = result
        row['timings_ms']['material_cut_and_log'] = (perf_counter() - cutting) * 1000
        if result['returncode']:
            row['status'] = 'geogram_failed'
            return row, None
        for remote, name in ((source_remote, 'source.obj'), (labels_remote, 'labels.json')):
            retrieve(engine.client, engine.sftp, remote, inputs / name)
        source = self.load_mesh(inputs / 'source.obj')
        bits = json.loads((inputs / 'labels.json').read_text(encoding='utf-8'))['operand_bits']
        cleaning = perf_counter()
        try:
            source, bits, cleanup = clean_for_backend(source, bits, branch)
        except ValueError as error:
            row.update(status='source_cleanup_rejected', cleanup_error=str(error))
            return row, None
        row['source_cleanup'] = cleanup
        maintenance_source, maintenance_labels = inputs / 'clean_source.obj', inputs / 'clean_labels.json'
        save_obj_fp64(source, maintenance_source)
        atomic_json(maintenance_labels, {'operand_bits': bits.tolist()})
        valid, metrics = self.validate(source, inputs / 'full_geometry_checks', 'source')
        # 退化候选先作局部清理，完整精确复审通过后重新绑定保存输入与来源。
        if branch == 'candidate' and metrics['zero_area_faces']:
            from degenerate_cleanup import repair_before_reject
            repaired, repaired_bits, repair = repair_before_reject(source, bits, self.validate, inputs / 'degenerate_cleanup')
            row['degenerate_input_cleanup'] = repair
            if repair['accepted']:
                source, bits = repaired, repaired_bits
                save_obj_fp64(source, maintenance_source)
                atomic_json(maintenance_labels, {'operand_bits': bits.tolist()})
                valid, metrics = self.validate(source, inputs / 'full_geometry_checks', 'source_after_degenerate_cleanup')
        row['input_metrics'] = metrics
        row['timings_ms']['cleanup_and_input_audit'] = (perf_counter() - cleaning) * 1000
        if not valid or (branch == 'full' and metrics['fp32_zero_area_faces']):
            row['status'] = 'maintenance_input_invalid'
            return row, None
        labels_valid = len(bits) == len(source.faces) and all(bit in (1, 2, 3) for bit in bits)
        if labels_valid:
            _, _, seam = source_region(source, bits, allow_shared=True)
            check = verify_labels(source, bits, self.load_mesh(parent), self.load_mesh(tool_path), seam, allow_shared=True)
            row['source_label_numerical_validation'] = check
            labels_valid = check['passed_1e_8_mm_numerical_check']
        row['source_labels_valid'], row['attempts'] = labels_valid, []
        accepted = None
        for method in self.quality.methods(branch, labels_valid):
            # 目录后缀保留旧外部契约识别规则，候选全量回退也要检查固定区域。
            destination = folder / (stem + '_' + method)
            quality_started = perf_counter()
            attempt = self.quality.run(maintenance_source, maintenance_labels, tool_path, method, destination)
            attempt['base_quality_wall_ms'] = (perf_counter() - quality_started) * 1000
            audit_started = perf_counter()
            attempt = self.quality.audit(maintenance_source, maintenance_labels, tool_path, destination, attempt)
            attempt['base_output_audit_wall_ms'] = (perf_counter() - audit_started) * 1000
            row['attempts'].append(attempt)
            if attempt['status'] != 'accepted_sampled':
                continue
            candidate = self.load_mesh(destination / 'candidate.obj')
            if reference is None:
                attempt['status'] = 'reference_unavailable'
                continue
            evaluation_started = perf_counter()
            geometry = global_geometry(candidate, reference)
            kept = preservation(candidate, initial, route, event)
            attempt.update(cumulative_geometry=geometry, preservation=kept,
                           geometry_policy='report_only_no_distance_stop',
                           reference_kind='independent_verified_prefix')
            row['timings_ms']['cumulative_geometry_and_preservation'] = (perf_counter() - evaluation_started) * 1000
            accepted = file_identity(destination / 'candidate.obj')
            row.update(selected_method=method, cumulative_geometry=geometry, preservation=kept,
                output_sha256=accepted['sha256'], output_file=accepted['path'],
                signed_removed_volume_mm3=float(initial.volume - candidate.volume))
            break
        row['status'] = 'published_under_sampled_and_vertex_protocol' if accepted else 'all_registered_attempts_rejected'
        row['frame_wall_including_audit_ms'] = (perf_counter() - started) * 1000
        return row, accepted

    def close(self):
        self.engine.close()
