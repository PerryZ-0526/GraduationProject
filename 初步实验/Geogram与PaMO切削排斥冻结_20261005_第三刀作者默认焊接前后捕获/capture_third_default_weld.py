"""第三刀同输入截取作者默认焊接前后对象，保持失败控制的原调用行为。"""
from pathlib import Path
import json,hashlib,shutil
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute,retrieve,save,now,PYTHON
project=Path.cwd();root=Path('D:/GraduationProject_切削排斥证据')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text('utf8'))
previous=project/'初步实验/Geogram与PaMO切削排斥冻结_20261005_第三刀严格焊接修复源阶段二三观测'
snapshot=project/'初步实验/Geogram与PaMO切削排斥冻结_20261005_第三刀作者默认焊接前后捕获'
snapshot.mkdir(exist_ok=False)
for name in ['sdf_bias_remesh.py','normalized_sdf_chain.py','normalized_working_source_gate.py']:
 shutil.copyfile(previous/name,snapshot/name)
worker=(previous/'stage2_only_worker.py').read_text('utf8')
needle='    model = pamo.PaMO(local, use_stage1=False, use_stage3=True)'
assert worker.count(needle)==1
observe='''    original_constructor = trimesh.Trimesh
    def observed_constructor(*args, **kwargs):
        result = original_constructor(*args, **kwargs)
        caller = inspect.currentframe().f_back
        if caller.f_code.co_filename == str(root / 'isolated_run_fp64.py') and 'vertices' in kwargs and 'faces' in kwargs:
            # 只观察作者构造结果，原函数参数和返回值不改，原失败仍须保留。
            source_mesh = original_constructor(kwargs['vertices'], kwargs['faces'], process=False)
            rows = []
            checker = '/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646'
            assert sha(checker) == '0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3'
            for name, value in [('stage2_before_default_weld.obj', source_mesh), ('stage2_after_default_weld.obj', result)]:
                path = out / name
                with path.open('w', encoding='utf8') as stream:
                    for point in np.asarray(value.vertices, np.float64) + origin:
                        stream.write('v ' + ' '.join(format(float(x), '.17g') for x in point) + '\\n')
                    for face in value.faces:
                        stream.write('f ' + ' '.join(str(int(x)+1) for x in face) + '\\n')
                check = subprocess.run([checker, str(path)], capture_output=True, text=True)
                rows.append({'file': name, 'sha256': sha(path), 'vertices': len(value.vertices), 'faces': len(value.faces), 'finite': bool(np.isfinite(value.vertices).all()), 'small_faces': int((value.area_faces <= 1e-12).sum()), 'watertight': bool(value.is_watertight), 'euler': int(value.euler_number), 'checker_returncode': check.returncode, 'embedding': json.loads(check.stdout) if check.returncode == 0 else None, 'checker_stderr': check.stderr})
            (out / '04-作者默认焊接前后实际对象.json').write_text(json.dumps({'生成时间': datetime.now(timezone(timedelta(hours=8))).isoformat(), '修改时间及修改内容': '首次生成，仅观察原作者默认焊接', '文档概述': '阶段二实际数组与原默认构造结果；原GPU失败未修改', '索引目录': ['rows'], 'rows': rows}, ensure_ascii=False, indent=2), 'utf8')
        return result
    trimesh.Trimesh = observed_constructor
'''
worker=worker.replace(needle,observe+needle)
compile(worker,str(snapshot/'stage2_only_worker.py'),'exec')
(snapshot/'stage2_only_worker.py').write_text(worker,'utf8')
shutil.copyfile(Path(__file__),snapshot/Path(__file__).name)
manifest=[{'file':p.name,'sha256':sha(p)} for p in sorted(snapshot.glob('*.py'))]
save(snapshot/'01-执行源码冻结清单.json',manifest)
prior=root/'20261005_第三刀严格焊接修复源阶段二三GPU对照'
output=root/'20261005_第三刀GPU作者默认焊接因果对象捕获';output.mkdir(exist_ok=False)
shutil.copyfile(prior/'inputs.json',output/'inputs.json')
source=root/'20261005_第三刀严格同坐标源原预算邻面修复开发/prepared_source.obj'
assert sha(source)==load(output/'inputs.json')['source_override']['sha256']
report=output/'01-默认焊接捕获执行终态.json'
record={'生成时间':now(),'修改时间及修改内容':'首次生成，同输入保持原失败的对象捕获','文档概述':'不计连续发布，不改作者默认焊接参数','索引目录':['bindings','execution'],'status':'running','new_publications':0,'bindings':{'source_sha256':sha(source),'previous_inputs_sha256':sha(prior/'inputs.json'),'manifest_sha256':sha(snapshot/'01-执行源码冻结清单.json')}}
save(report,record)
e=RemoteQuality(output,14137)
try:
 assert execute(e.client,['mkdir',e.remote])['returncode']==0
 for path in [snapshot/r['file'] for r in manifest]+[output/'inputs.json',source]:
  remote=e.remote+'/'+('source.obj' if path==source else path.name)
  e.sftp.put(str(path),remote);assert execute(e.client,['sha256sum',remote])['stdout'].split()[0]==sha(path)
 run=execute(e.client,['env','LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6',PYTHON,e.remote+'/stage2_only_worker.py'],e.remote+'/stdout.log',timeout=900)
 retrieve(e.client,e.sftp,e.remote+'/stdout.log',output/'stdout.log')
 for name in ['04-作者默认焊接前后实际对象.json','stage2_before_default_weld.obj','stage2_after_default_weld.obj']:
  try:retrieve(e.client,e.sftp,e.remote+'/result/'+name,output/name)
  except FileNotFoundError:record.setdefault('missing_outputs',[]).append(name)
 for name in ['04-完整求解前实际工作源门控.json','01-CUDA初始编码源.obj','02-CUDA再中心化碰撞源.obj','03-整理后归一化SDF源.obj']:
  try:retrieve(e.client,e.sftp,e.remote+'/result/working_sources/'+name,output/name)
  except FileNotFoundError:record.setdefault('missing_outputs',[]).append(name)
 record.update(status='completed_with_recorded_outcomes',execution=run,finished_beijing=now());save(report,record)
 if (output/'04-作者默认焊接前后实际对象.json').exists():print(load(output/'04-作者默认焊接前后实际对象.json')['rows'],flush=True)
 else:print(record,flush=True)
finally:e.close()
