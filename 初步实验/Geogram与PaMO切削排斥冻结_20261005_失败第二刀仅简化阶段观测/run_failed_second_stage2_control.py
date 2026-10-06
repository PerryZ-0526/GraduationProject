"""在同一失败第二刀物理源上只观测作者简化阶段，不运行安全投影。"""
from pathlib import Path
import json
import hashlib
import shutil
import importlib.util
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, retrieve, save, now, PYTHON
import trimesh

project = Path.cwd()
root = Path('D:/GraduationProject_切削排斥证据')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_text('utf8'))
batch = root / '20261005_精确源阶段二三薄壁完整32刀开发上传修订/薄壁_00_长序列'
row = load(batch / '01-统一配置完整父反馈记录.json')['rows'][1]
source = batch / '薄壁_00_长序列_e1_candidate_input/clean_source.obj'
reference = batch / '薄壁_00_长序列_e1_reference/validated_reference.obj'
assert sha(source) == row['attempt']['inputs_sha256']['source.obj']
output = root / '20261005_薄壁阶段二三连续第二刀仅简化退化定位'
output.mkdir(exist_ok=False)
previous = project / '初步实验/Geogram与PaMO切削排斥冻结_20261005_新实例薄壁第三刀关闭阶段一观测_v2'
snapshot = project / '初步实验/Geogram与PaMO切削排斥冻结_20261005_失败第二刀仅简化阶段观测'
snapshot.mkdir(exist_ok=False)
for name in ['sdf_bias_remesh.py', 'normalized_sdf_chain.py', 'normalized_working_source_gate.py']:
    shutil.copyfile(previous / name, snapshot / name)
worker = (previous / 'thin_stage_worker.py').read_text('utf8')
assert worker.count('use_stage1=False, use_stage3=True') == 1
worker = worker.replace('use_stage1=False, use_stage3=True', 'use_stage1=False, use_stage3=False')
worker = worker.replace("'use_stage3': True", "'use_stage3': False").replace("'stage3': 1", "'stage3': 0")
worker = worker.replace("    from thin_full_stage_observation import install_stage_observation\n    install_stage_observation(out / 'stage_observations', origin)\n", '')
spec = importlib.util.spec_from_file_location('stage2_budget_math', previous.parent / 'Geogram与PaMO切削排斥冻结_20261005_自动面分离R640完整反馈/simplification_budget_ratio.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
target, ratio = module.target_budget(len(trimesh.load(source, process=False).faces), len(trimesh.load(reference, process=False).faces))
assert worker.count('ratio=1.1419558359621451, min_verts=0') == 1
worker = worker.replace('ratio=1.1419558359621451, min_verts=0', 'ratio=' + repr(ratio) + ', min_verts=0')
worker = worker.replace('01-薄壁第三刀同源分辨率三阶段观测终态.json', '01-第二刀仅简化阶段终态.json')
worker = worker.replace('作者关闭阶段一选项，同源简化和安全投影，不是维护发布', '仅作者简化阶段，同一失败第二刀源；不运行安全投影，不是发布')
compile(worker, str(snapshot / 'stage2_only_worker.py'), 'exec')
(snapshot / 'stage2_only_worker.py').write_text(worker, 'utf8')
shutil.copyfile(Path(__file__), snapshot / Path(__file__).name)
manifest = [{'file': p.name, 'sha256': sha(p)} for p in sorted(snapshot.glob('*.py'))]
save(snapshot / '01-执行源码冻结清单.json', manifest)
inputs = load(root / '20261005_新实例薄壁第三刀同源关闭阶段一GPU控制_v2/inputs.json')
inputs.update(source_override={'file': 'source.obj', 'sha256': sha(source)}, origin_override_mm=row['origin_mm'], minimum_sdf_resolution=640)
save(output / 'inputs.json', inputs)
save(output / '01-仅简化控制执行登记.json', {'生成时间': now(), '修改时间及修改内容': '首次生成，同一失败第二刀阶段隔离', '文档概述': '阶段调用0/1/0，不混入连续发布或原三阶段统计', '索引目录': ['bindings'], 'status': 'running', 'target_faces': target, 'bindings': {'source_sha256': sha(source), 'reference_sha256': sha(reference), 'manifest_sha256': sha(snapshot / '01-执行源码冻结清单.json')}})
engine = RemoteQuality(output, 14137)
try:
    assert execute(engine.client, ['mkdir', engine.remote])['returncode'] == 0
    for path in [snapshot / r['file'] for r in manifest] + [output / 'inputs.json', source]:
        remote = engine.remote + '/' + ('source.obj' if path == source else path.name)
        engine.sftp.put(str(path), remote)
        assert execute(engine.client, ['sha256sum', remote])['stdout'].split()[0] == sha(path)
    log = engine.remote + '/stdout.log'
    run = execute(engine.client, ['env', 'LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6', PYTHON, engine.remote + '/stage2_only_worker.py'], log, timeout=900)
    retrieve(engine.client, engine.sftp, log, output / 'stdout.log')
    save(output / '02-实际执行终态.json', {'生成时间': now(), '修改时间及修改内容': '首次生成，实际退出记录', '文档概述': '仅GPU简化，无安全投影', '索引目录': ['execution'], 'execution': run})
    assert run['returncode'] == 0
    for name in ['01-第二刀仅简化阶段终态.json', 'raw_full_candidate.obj']:
        retrieve(engine.client, engine.sftp, engine.remote + '/result/' + name, output / name)
    terminal = load(output / '01-第二刀仅简化阶段终态.json')
    assert terminal['output_sha256'] == sha(output / 'raw_full_candidate.obj')
    print({k: terminal[k] for k in ['stage_calls', 'finite', 'zero_or_small_faces', 'euler', 'components', 'embedding']}, flush=True)
finally:
    engine.close()
