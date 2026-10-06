"""复用另一研究线路的21份已见Geogram源及真实标签，独立冻结本批输入。"""
import hashlib
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta
import numpy as np
import trimesh

ROOT=Path('D:/GraduationProject实验输出/20261006_实时预算局部质量算法')
SOURCE=Path('D:/GraduationProject_切削排斥证据/20261006_Geogram变化面触发共享边质量生成/23-变化面方法与十五开发输入冻结清单.json')
manifest=json.loads(SOURCE.read_text(encoding='utf-8'))
ROOT.mkdir(exist_ok=True)
(ROOT/'inputs').mkdir(exist_ok=False)
cases=[]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def signatures(mesh):
    return [tuple(sorted(tuple(x) for x in tri)) for tri in mesh.vertices[mesh.faces]]
for index,case in enumerate(manifest['cases']):
    for name in ('source','labels','parent','tool'):
        assert sha(Path(case[name]))==case['sha256'][name]
    source,parent,tool=[trimesh.load(case[k],process=False) for k in ('source','parent','tool')]
    bits=np.array(json.loads(Path(case['labels']).read_text(encoding='utf-8'))['operand_bits'])
    inherited=set(signatures(parent))|set(signatures(tool))
    active=np.array([key not in inherited for key in signatures(source)])
    path=ROOT/'inputs'/f'case{index:02d}.npz'
    np.savez(path,vertices=source.vertices,faces=source.faces,bits=bits,active=active)
    assert len(bits)==len(source.faces)
    cases.append(dict(id=f'case{index:02d}',name=case['id'],kind=case['kind'],file=str(path.relative_to(ROOT)),sha256=sha(path),original=case,
        faces=len(bits),active_faces=int(active.sum()),identity='已见开发/失败帧复用，不恢复独立评价身份'))
report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),source_manifest_sha256=sha(SOURCE),
    protocol=dict(budgets_ms=[1,5,10,20],rounds=3,max_candidates=128,max_flips=16,geometry='精确共面凸两面片，固定顶点与外部面',scope='静态Geogram源面维护；不是连续切削或渲染延迟'),cases=cases)
(ROOT/'02-输入与研究预算冻结.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(cases=len(cases),faces=[x['faces'] for x in cases]),ensure_ascii=False))
