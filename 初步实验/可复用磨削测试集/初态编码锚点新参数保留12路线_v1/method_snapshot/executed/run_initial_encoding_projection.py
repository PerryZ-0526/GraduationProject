"""初态编码退化锚点完整投影诊断，保留全量碰撞和保存对象门控。"""
import argparse
from pathlib import Path
from run_anchored_geometry_diagnostic import AnchoredEngine
from run_constrained_batch import HERE
from preserved_controller_source import replace_once
from preserved_feedback_gate import audit_preserved_candidate
from run_geometry_study import save, now
from audit_followup_candidate import sha256


class InitialEncodingEngine(AnchoredEngine):
    def setup(self):
        info = super().setup()
        name = 'encoded_degenerate_anchors.py'
        (self.output/name).write_bytes((HERE/name).read_bytes())
        self.sftp.put(str(HERE/name), self.remote+'/'+name)
        worker = (self.output/'run_anchored_worker.py').read_text(encoding='utf-8')
        # 新方法自动识别编码退化邻域；旧方法与历史冻结副本保持原前提。
        worker = replace_once(worker,
            '        details["fixed_geometry_arithmetic_precondition"] = require_fixed_degenerate_faces(',
            '        from encoded_degenerate_anchors import initial_encoding_anchors\n'
            '        fixed, details["initial_encoding_anchors"] = initial_encoding_anchors(mesh.vertices, mesh.faces, fixed, geometry_scale, geometry_translation)\n'
            '        details["fixed_geometry_arithmetic_precondition"] = require_fixed_degenerate_faces(')
        path = self.output/'initial_encoding_worker.py'
        path.write_text(worker, encoding='utf-8')
        self.sftp.put(str(path), self.remote+'/run_constrained_worker.py')
        info.update(initial_encoding_rule_sha256=sha256(HERE/name), actual_initial_encoding_worker_sha256=sha256(path))
        return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'labels', 'tool', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    engine = InitialEncodingEngine(args.output, args.port)
    record = dict(time_beijing=now(), status='running', published=False, rows=[],
        input_sha256={name:sha256(getattr(args,name)) for name in ('source','labels','tool')})
    path = args.output/'01-初态编码锚点完整投影诊断.json'
    try:
        record['environment'] = engine.setup()
        save(path, record)
        for method in ('boolean', 'expanded'):
            folder = args.output/method
            row = engine.run(args.source, args.labels, args.tool, method, folder)
            row = audit_preserved_candidate(engine, args.source, args.tool, args.labels, folder, row)
            record['rows'].append(row)
            save(path, record)
            print(method, row['status'], row.get('numerical_diagnostic'), flush=True)
        record.update(status='completed_with_recorded_outcomes', finished_beijing=now())
        save(path, record)
    finally:
        engine.close()
