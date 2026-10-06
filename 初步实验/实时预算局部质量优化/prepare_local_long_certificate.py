"""复用冻结的完整长轨迹，接入本机自适应方向认证和共享质量拓扑。"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


BASE = Path(__file__).resolve().parent
ROOT = Path('D:/GraduationProject实验输出/20261007_自适应方向认证本机完整长轨迹')
METHOD = Path('D:/GraduationProject实验输出/20261007_自适应方向认证完整父反馈')
ARCHIVE = Path('D:/GraduationProject实验输出/20261007_常驻局部质量完整长轨迹_14137_v10/11-常驻长轨迹完整执行与复审证据.zip')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    assert sha(ARCHIVE) == 'f60ee87f724a73a58fe1c658306583ca19d88ad286f9c0e17f4e234906a2d048'
    identity = json.loads((METHOD/'01-自适应方向完整反馈准备与实际版本.json').read_text(encoding='utf-8'))
    for name, digest in identity['frozen_files'].items():
        assert sha(METHOD/name) == digest, name
    assert not ROOT.exists()
    ROOT.mkdir()
    shutil.copytree(METHOD/'workers', ROOT/'workers')
    # 原输入及必要修复参数逐字节恢复，旧方法身份另存，不冒充当前实现。
    with zipfile.ZipFile(ARCHIVE) as archive:
        for name in archive.namelist():
            if name.startswith('inputs/') or name in ('manifest.json', 'run_config.json', 'resident_source_cleanup.py', 'resident_long_worker.py'):
                target = ROOT/name
                assert target.resolve().is_relative_to(ROOT.resolve())
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
        audit_name = next(name for name in archive.namelist() if name.startswith('audit_resident_long_arrays_'))
        (ROOT/'audit_local_long_arrays.py').write_bytes(archive.read(audit_name))
    config_path = ROOT/'run_config.json'
    shutil.copyfile(config_path, ROOT/'run_config_original.json')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config['source_certificate_override'] = dict(method='windows_array_shared_topology_adaptive_directional', trigger_pairs=32768,
                                               source_identity_sha256=sha(METHOD/'01-自适应方向完整反馈准备与实际版本.json'))
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    workers = ROOT/'workers'
    (workers/'build_identity.json').write_text(json.dumps(dict(status='completed', libraries=[dict(path=str(p), sha256=sha(p)) for p in workers.glob('*.dll')]), indent=2), encoding='utf-8')
    # 仅适配本机执行与完整方法绑定，不改修复、翻边和源认证规则。
    entry = ROOT/'resident_long_worker.py'
    shutil.copyfile(entry, ROOT/'resident_long_worker_original.py')
    text = entry.read_text(encoding='utf-8')
    text = text.replace("('.py','.cpp','.so','.json')", "('.py','.cpp','.so','.dll','.h','.json')")
    text = text.replace("'--edge-backend','cuda','--certified-operand-pairs'", "'--edge-backend','cpu','--certified-operand-pairs','--linear-unique-facets'")
    text = text.replace('CUDA活动边准备', 'CPU共享拓扑活动边准备')
    text = text.replace('CUDA维护及数组复制', 'CPU维护及数组复制')
    text = text.replace('.read_text())', ".read_text(encoding='utf-8'))")
    entry.write_text(text, encoding='utf-8')
    audit = ROOT/'audit_local_long_arrays.py'
    audit.write_text(audit.read_text(encoding='utf-8').replace('.read_text())', ".read_text(encoding='utf-8'))"), encoding='utf-8')
    manifest = json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    for route in manifest['routes']:
        assert len(route['prefix_tools']) == 384
        assert sha(ROOT/'inputs'/route['initial_mesh']) == route['initial_mesh_sha256']
        for tool in route['prefix_tools']:
            assert sha(ROOT/'inputs'/tool['mesh']) == tool['sha256']
    record = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(), status='completed',
                  input_archive_sha256=sha(ARCHIVE), original_method_identity_sha256=sha(METHOD/'01-自适应方向完整反馈准备与实际版本.json'),
                  planned_candidate_events=768, planned_reference_events=768, hardware_scope='本机CPU维护；后续Intel Arc实际像素另测',
                  files={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    (ROOT/'00-完整长轨迹输入与本机方法冻结.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='prepared', root=str(ROOT), frozen_files=len(record['files']), planned_events=1536), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
