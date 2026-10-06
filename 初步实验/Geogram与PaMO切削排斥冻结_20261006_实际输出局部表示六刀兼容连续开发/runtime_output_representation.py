"""修正阶段按当前声明原点核对实际GPU输出表示，按物理摘要复用同一刀证据。"""
from pathlib import Path
from contextlib import contextmanager
import numpy as np
from locality_masks import save_obj_fp64
from run_geometry_study import execute, retrieve, save, now, PYTHON
from exact_embedding_gate import stored_mesh_sha256
from explicit_output_representation_gate import audit_output_representation, sha256


class RuntimeOutputRepresentation:
    def __init__(self, engine, output, origin, scale, stage3_remote_record=None):
        self.engine, self.output = engine, Path(output)
        self.origin = list(origin)
        self.scale = None if scale is None else float(scale)
        self.stage3_remote_record = stage3_remote_record
        self.cache = {}

    def __call__(self, mesh, certificate):
        # 连续入口在求解完成后读取本刀实际尺度，禁止猜测或沿用上一刀尺度。
        if self.scale is None:
            import json
            with self.engine.sftp.open(self.stage3_remote_record, 'r') as stream:
                stage = json.load(stream)
            if stage['status'] != 'completed_original_solver':
                return False, {'accepted': False, 'reason': 'actual_stage3_not_completed'}
            self.scale = float(stage['scale'])
        digest = stored_mesh_sha256(mesh)
        if digest in self.cache:
            return self.cache[digest]
        local = self.output / digest
        local.mkdir(parents=True, exist_ok=False)
        source = local / 'candidate.obj'
        save_obj_fp64(mesh, source)
        assert sha256(source) == digest
        config = {'scale': self.scale, 'origins': [('tool', self.origin)]}
        save(local / 'config.json', config)
        engine = self.engine
        remote = engine.remote + '/output_representation_' + digest
        assert execute(engine.client, ['mkdir', remote])['returncode'] == 0
        worker = Path(__file__).with_name('output_representation_probe_worker.py')
        bindings = []
        for path, name in [(source, 'candidate.obj'), (local / 'config.json', 'config.json'), (worker, 'worker.py')]:
            engine.sftp.put(str(path), remote + '/' + name)
            assert execute(engine.client, ['sha256sum', remote + '/' + name])['stdout'].split()[0] == sha256(path)
            bindings.append({'file': str(path), 'sha256': sha256(path)})
        execution = execute(engine.client, ['env', 'LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6',
                                            PYTHON, remote + '/worker.py'], remote + '/stdout.log', timeout=300)
        record = {'生成时间': now(), '修改时间及修改内容': '当前刀输出表示首次执行',
                  '文档概述': '实际GPU张量读回及全量嵌入检查，不重跑PaMO求解',
                  '索引目录': ['bindings', 'execution'], 'bindings': bindings, 'execution': execution,
                  'remote': remote, 'new_full_GPU_solver_calls': 0, 'new_publications': 0}
        save(local / '02-实际表示绑定与GPU执行.json', record)
        for name in engine.sftp.listdir(remote):
            if name.endswith(('.json', '.obj', '.log')) and name != 'candidate.obj':
                retrieve(engine.client, engine.sftp, remote + '/' + name, local / name)
        # GPU或证据生成失败正常拒绝，不能回退为仅CPU模拟编码成功。
        if execution['returncode']:
            result = False, {'accepted': False, 'reason': 'actual_GPU_output_encoding_execution_failed',
                             'execution': execution, 'evidence_folder': str(local)}
        else:
            accepted, details = audit_output_representation(mesh, certificate, local, 'tool')
            details.update(evidence_folder=str(local), physical_sha256=digest,
                           declared_origin_mm=self.origin, declared_scale=self.scale)
            result = accepted, details
        self.cache[digest] = result
        return result


@contextmanager
def output_representation_context(engine, output, origin, scale):
    """仅对本刀排斥修正及最终输出复审启用，退出后恢复旧门控。"""
    import exact_embedding_gate as gate
    previous = gate.ACTUAL_OUTPUT_REPRESENTATION_GUARD
    gate.ACTUAL_OUTPUT_REPRESENTATION_GUARD = RuntimeOutputRepresentation(engine, output, origin, scale)
    try:
        yield gate.ACTUAL_OUTPUT_REPRESENTATION_GUARD
    finally:
        gate.ACTUAL_OUTPUT_REPRESENTATION_GUARD = previous
