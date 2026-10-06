"""封存完整新批次及其继承输入、底层库与源码；渲染运行依赖以完整轮子保留。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
import zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();base=Path(json.loads((root/'01-紧凑短边修复完整GPU批次执行记录.json').read_text())['baseline'])
    summary=json.loads((root/'03-三轮四预算与真实GPU像素终态汇总.json').read_text());assert summary['status']=='completed'
    assert json.loads((Path(summary['render_root'])/'01-私有GPU渲染依赖与完整反馈执行记录.json').read_text())['status'] in ['completed','failed']
    sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest();files={}
    for path in root.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and 'python_deps' not in path.parts:
            files[root.name+'/'+str(path.relative_to(root))]=path
    # 继承的实际输入和Geogram底层库没有重编译，独立封存其路径与字节。
    for path in (base/'inputs').rglob('*'):
        if path.is_file():files[base.name+'/'+str(path.relative_to(base))]=path
    for name in ['geogram.zip','opennl.zip','amgcl.zip','libmeshb.zip','rply.zip']:
        files[base.name+'/'+name]=base/name
    for row in json.loads((root/'workers/build_identity.json').read_text())['libraries']:
        path=Path(row['path']);assert sha(path)==row['sha256']
        if path.is_relative_to(base):files[base.name+'/'+str(path.relative_to(base))]=path
    # 启动脚本和控制台失败现场也保留，不仅保存成功网格。
    for name in ['run_compact_repair_trials_20261006.py','run_private_gpu_render_trials_20261006.py',
                 'render_live_gpu_feedback_20261006.py','collect_compact_repair_results_20261006.py',
                 'compact_short_repair_20261006.log','compact_short_render_20261006.log',
                 'compact_short_repair_20261006_start.json','compact_short_render_20261006_start.json',
                 'run_private_gpu_render_trials_20261006_retry2.py','compact_short_render_20261006_retry2.log',
                 'compact_short_render_20261006_retry2_start.json']:
        path=root.parent/name;files['启动与驱动/'+name]=path
    files['启动与驱动/'+Path(__file__).name]=Path(__file__)
    inventory=[dict(name=name,size=path.stat().st_size,sha256=sha(path)) for name,path in sorted(files.items())]
    archive=root.parent/'compact_short_repair_full_evidence_20261006.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for name,path in sorted(files.items()):z.write(path,name)
        z.writestr('完整证据逐文件清单.json',json.dumps(inventory,ensure_ascii=False,indent=2))
    receipt=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),path=str(archive),size=archive.stat().st_size,
        sha256=sha(archive),members=len(inventory)+1,files=len(inventory),
        excluded=['Python字节码缓存','解包Python依赖目录，完整安装轮子已包含'],
        scope='完整实际输出、所有拒绝/受阻与复审、方法字节和继承输入库；系统驱动与Python基础环境另备')
    (root/'04-完整短边修复与GPU像素证据归档回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
