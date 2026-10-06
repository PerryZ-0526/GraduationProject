"""封存缓存源认证完整新批次，明确绑定既有主包与运行库补包作为恢复前提。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
import zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();summary=json.loads((root/'06-缓存源认证三轮四预算与真实像素终态汇总.json').read_text())
    assert summary['status']=='completed'
    sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest();files={}
    for path in root.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:files[root.name+'/'+str(path.relative_to(root))]=path
    # 原34项控制的实际源也保留；大体积继承输入和渲染运行环境由已核对前提包恢复。
    diagnosis=root.parent/'geogram_budget_full_20261006/diagnosis'
    for name in ['raw.npz','native_repaired_20.obj','native_repaired_50.obj','native_repaired_100.obj','native_repaired_200.obj']:
        files['geogram_budget_full_20261006/diagnosis/'+name]=diagnosis/name
    for name in ['run_cached_certificate_trials_20261006.py','resume_cached_certificate_trials_20261006.py',
                 'collect_cached_certificate_results_20261006.py','cached_certificate_trials_20261006.log',
                 'cached_certificate_trials_resume_20261006.log','cached_certificate_trials_20261006_start.json',
                 'cached_certificate_trials_resume_20261006_start.json']:
        files['启动与驱动/'+name]=root.parent/name
    files['启动与驱动/'+Path(__file__).name]=Path(__file__)
    inventory=[dict(name=name,size=path.stat().st_size,sha256=sha(path)) for name,path in sorted(files.items())]
    prerequisites=[dict(name='05-紧凑短边修复四预算与GPU像素完整证据.zip',sha256='f13d575dff2e095d6435fcdbb5a38969b0261adaf1e9c062202fa4cfb9ef4569'),
        dict(name='06-紧凑修复继承Geogram动态库名称补充.zip',sha256='bba4faf45400fed3a829196cdc485e26148d87b909599b574bce46bb5550f5b0')]
    archive=root.parent/'cached_source_certificate_full_evidence_20261006.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for name,path in sorted(files.items()):z.write(path,name)
        z.writestr('完整证据逐文件清单.json',json.dumps(inventory,ensure_ascii=False,indent=2))
        z.writestr('继承运行与输入前提包.json',json.dumps(prerequisites,ensure_ascii=False,indent=2))
    receipt=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),path=str(archive),size=archive.stat().st_size,
        sha256=sha(archive),members=len(inventory)+2,files=len(inventory),prerequisites=prerequisites,
        scope='本版本所有实际执行文件、完整新输出与失败现场；恢复必须同时具备已绑定的05和06前提包，系统基础环境另备')
    (root/'07-缓存源认证完整新批次归档回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
