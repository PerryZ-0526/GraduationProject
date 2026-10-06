"""封存过滤精确谓词完整新批次，绑定先前三份完整归档作为运行与控制输入前提。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
import zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();summary=json.loads((root/'06-过滤精确谓词三轮四预算与真实像素终态汇总.json').read_text())
    assert summary['status']=='completed'
    sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest();files={}
    for path in root.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:files[root.name+'/'+str(path.relative_to(root))]=path
    # 两轮内部阶段诊断完整保留；首轮日志绑定失败不替换，第二轮须实际完成核对。
    for name in ['geogram_native_stage_profile_20261006','geogram_native_stage_profile_20261006_r2']:
        profile=root.parent/name
        assert (profile/'01-Geogram内部阶段实际计时与输入绑定.json').exists()
        for path in profile.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:files[name+'/'+str(path.relative_to(profile))]=path
    assert json.loads((root.parent/'geogram_native_stage_profile_20261006_r2/02-Geogram内部阶段日志核对与汇总.json').read_text())['all_main_stages_bound']
    # 原控制输入与继承运行依赖由已核对前提包恢复，实际新运行文件全部另存。
    for name in ['run_filtered_certificate_trials_20261006.py','collect_filtered_certificate_results_20261006.py',
                 'filtered_certificate_trials_20261006.log','filtered_certificate_trials_20261006_start.json',
                 'profile_geogram_native_stages_20261006.py','profile_geogram_native_stages_r2_20261006.py',
                 'geogram_native_stage_profile_20261006.log','geogram_native_stage_profile_20261006_r2.log',
                 'geogram_native_stage_profile_20261006_start.json','geogram_native_stage_profile_20261006_r2_start.json',
                 'collect_geogram_stage_profile_20261006.py']:
        files['启动与驱动/'+name]=root.parent/name
    files['启动与驱动/'+name]=root.parent/name
    files['启动与驱动/'+Path(__file__).name]=Path(__file__)
    inventory=[dict(name=name,size=path.stat().st_size,sha256=sha(path)) for name,path in sorted(files.items())]
    prerequisites=[dict(name='05-紧凑短边修复四预算与GPU像素完整证据.zip',sha256='f13d575dff2e095d6435fcdbb5a38969b0261adaf1e9c062202fa4cfb9ef4569'),
        dict(name='06-紧凑修复继承Geogram动态库名称补充.zip',sha256='bba4faf45400fed3a829196cdc485e26148d87b909599b574bce46bb5550f5b0'),
        dict(name='07-缓存源认证四预算与GPU像素完整证据.zip',sha256='012d9184ed3459e08c8f07f7d766f6d926c8ed88cfb15c5ee2bd36b57651249d')]
    archive=root.parent/'filtered_source_certificate_full_evidence_20261006.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for name,path in sorted(files.items()):z.write(path,name)
        z.writestr('完整证据逐文件清单.json',json.dumps(inventory,ensure_ascii=False,indent=2))
        z.writestr('继承运行与输入前提包.json',json.dumps(prerequisites,ensure_ascii=False,indent=2))
    receipt=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),path=str(archive),size=archive.stat().st_size,
        sha256=sha(archive),members=len(inventory)+2,files=len(inventory),prerequisites=prerequisites,
        scope='本版本所有实际执行文件、完整新输出与失败现场；恢复必须同时具备已绑定的05、06和07前提包，系统基础环境另备')
    (root/'07-过滤精确谓词完整新批次归档回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
