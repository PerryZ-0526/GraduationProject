"""同次浅磨输入比较原版、两种CGAL方法和当前共面局部候选。"""
import getpass
from pathlib import Path
import sys
from audit_followup_candidate import sha256
from ordered_physical_cleanup import SOURCE as CLEANUP_SOURCE
from preserved_controller_source import replace_once
from preserved_feedback_gate import audit_preserved_candidate, check_preserved_mesh
from run_constrained_batch import RemoteQuality, audit_candidate, HERE
from run_initial_encoding_projection import InitialEncodingEngine


class FeatureEngines:
    """两种实际工作器隔离运行，共用同一浅磨CSG与清理输入。"""
    def __init__(self, output, port):
        self.output = Path(output)
        for name in ('baseline', 'candidate'):
            (self.output/name).mkdir()
        original = getpass.getpass
        credential = original('GPU SSH password: ')
        # 两次认证只在本进程内复用密码，结束构造后恢复原接口，不写入记录。
        getpass.getpass = lambda *args, **kwargs: credential
        try:
            self.baseline = RemoteQuality(self.output/'baseline', port)
            self.candidate = InitialEncodingEngine(self.output/'candidate', port)
        finally:
            getpass.getpass = original
            del credential
        self.client, self.sftp, self.remote = self.baseline.client, self.baseline.sftp, self.baseline.remote

    def setup(self):
        info = dict(baseline=self.baseline.setup(), candidate=self.candidate.setup(),
            methods=dict(full='作者PaMO完整三阶段', global_='CGAL全量与原GPU投影',
                spatial='CGAL空间局部与原GPU投影', boolean='Triangle共面区域与固定锚点完整GPU投影'))
        for name in ('run_ordered_features.py', 'ordered_physical_cleanup.py'):
            (self.output/name).write_bytes((HERE/name).read_bytes())
        path = self.output/'ordered_physical_cleanup_snapshot.py'
        path.write_text(CLEANUP_SOURCE, encoding='utf-8')
        info['feature_source_sha256'] = {name:sha256(self.output/name) for name in (
            'run_ordered_features.py', 'ordered_physical_cleanup.py', 'ordered_physical_cleanup_snapshot.py', 'ordered_features_snapshot.py')}
        return info

    def run(self, source, labels, tool, method, folder):
        engine = self.candidate if method == 'boolean' else self.baseline
        row = engine.run(source, labels, tool, method, folder)
        row['feature_method'] = method
        return row

    def audit(self, source, tool, labels, folder, row):
        if row['feature_method'] == 'boolean':
            return audit_preserved_candidate(self.candidate, source, tool, labels, folder, row)
        row = audit_candidate(source, tool, labels, folder, row)
        if not row['execution']['returncode']:
            import trimesh
            mesh = trimesh.load(Path(folder)/'candidate.obj', process=False)
            valid, metrics = check_preserved_mesh(self.baseline, Path(folder)/'full_geometry_checks', mesh, 'candidate')
            row['output_metrics']['full_exact_embedding'] = metrics.get('full_exact_embedding')
            if not valid:
                row['status'] = 'full_embedding_rejected'
        return row

    def close(self):
        self.candidate.close()
        self.baseline.close()


def build_feature_source():
    """保留原工具、完整分母与失败记录，仅明确新方法入口及公共输入契约。"""
    source = (HERE/'run_constrained_features.py').read_text(encoding='utf-8')
    source = 'from ordered_physical_cleanup import clean_for_backend\nfrom preserved_feedback_gate import local_fp64_valid\n'+source
    source = replace_once(source, 'source, bits, cleanup = clean_provenance(source, bits)',
        "source, bits, cleanup = clean_for_backend(source, bits, 'candidate')")
    source = source.replace('("full", "spatial", "boolean")', '("full", "global", "spatial", "boolean")')
    source = replace_once(source, 'valid, checks = mesh_valid(source)', 'valid, checks = local_fp64_valid(source)')
    # 原后端无编码退化固定契约；其前提保留，新候选交原固定后端独立验证。
    source = replace_once(source, 'if not valid or checks["fp32_zero_area_faces"]:',
        'if not valid or (method != "boolean" and checks["fp32_zero_area_faces"]):')
    source = replace_once(source, 'row = audit_candidate(source_path, tool, labels_path, destination, row)',
        'row = engine.audit(source_path, tool, labels_path, destination, row)')
    return source


if __name__ == '__main__':
    output = Path(sys.argv[sys.argv.index('--output')+1])
    if output.exists():
        raise FileExistsError(output)
    # 原main负责创建输出目录，实际执行快照先保存在独立入口目录。
    folder = HERE/'实验结果/小特征新入口冻结副本'/output.name
    folder.mkdir(parents=True, exist_ok=False)
    path = folder/'ordered_features_snapshot.py'
    source = build_feature_source()
    path.write_text(source, encoding='utf-8')
    namespace = dict(__name__='ordered_features_snapshot', __file__=str(path))
    exec(compile(source, str(path), 'exec'), namespace)
    # 在setup前复制同次执行源码；不提前创建原main负责的输出目录。
    original_setup = FeatureEngines.setup
    def setup(self):
        (self.output/'ordered_features_snapshot.py').write_bytes(path.read_bytes())
        return original_setup(self)
    FeatureEngines.setup = setup
    namespace['RemoteQuality'] = FeatureEngines
    namespace['main']()
