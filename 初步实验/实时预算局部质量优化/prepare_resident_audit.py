"""按真实父反馈记录打包全部保存对象，包含拒绝源和规范化中间网格。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--through-step',type=int)
    args=parser.parse_args();p=args.root/'01-实际常驻切削与预算维护父链诊断.json'
    record=json.loads(p.read_text(encoding='utf-8'));assert record['status']=='terminal_diagnostic_pending_embedding_audit'
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    plan={'record_sha256':sha(p),'planned_events':sum(r['planned_events'] for r in record['routes']),
          'audited_through_step':args.through_step,'files':[]}
    with zipfile.ZipFile(args.root/'audit_inputs.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for route in record['routes']:
            for event in route['events']:
                if args.through_step is not None and event['step']>args.through_step:continue
                for stage in ('raw','cleaned','output'):
                    if stage not in event:continue
                    f=Path(event[stage]);assert sha(f)==event[stage+'_sha256'];name=f'budget{route["budget_ms"]}_{f.name}'
                    plan['files'].append(dict(budget_ms=route['budget_ms'],step=event['step'],stage=stage,file=name,sha256=sha(f)))
                    z.write(f,name)
        z.writestr('plan.json',json.dumps(plan,ensure_ascii=False,indent=2))
    # 冻结本次实际调用源码、原生库及构建配置，不覆盖历史副本。
    snapshot=args.root/'实际执行源码副本';snapshot.mkdir(exist_ok=False)
    workspace=Path(__file__).resolve().parents[2]
    files=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).with_name('geogram_memory.cpp'),
        Path(__file__).parent/'本机内存布尔编译/CMakeLists.txt',workspace/'tmp/实时预算内存布尔编译/Release/geogram_memory.dll',
        workspace/'tmp/实时预算Geogram本机编译/bin/Release/geogram.dll']
    for f in files:shutil.copy2(f,snapshot/f.name)
    plan['frozen_sources']={f.name:sha(f) for f in files};plan['package_sha256']=sha(args.root/'audit_inputs.zip')
    (args.root/'03-全量保存审计计划与实际源码冻结.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'objects':len(plan['files']),'zip_bytes':(args.root/'audit_inputs.zip').stat().st_size,'sha256':plan['package_sha256']}))


if __name__=='__main__':main()
