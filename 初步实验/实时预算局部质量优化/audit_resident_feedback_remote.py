"""复审实际常驻诊断的每个保存源及输出，不将阻断后缀计为完成。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--checker',type=Path,required=True);args=parser.parse_args()
    args.root.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    with zipfile.ZipFile(args.package) as z:
        # 只解压预先按基础文件名打包的本任务对象，拒绝路径穿越和重名。
        names=z.namelist();assert len(names)==len(set(names))
        assert all(Path(n).name==n and n not in ('..','.') for n in names)
        plan=json.loads(z.read('plan.json'));rows=[]
        for item in plan['files']:
            # 磁盘紧张时每次只展开一个已校验对象，终态审计后删除这个临时副本。
            mesh=args.root/item['file'];mesh.write_bytes(z.read(item['file']));assert sha(mesh)==item['sha256']
            start=perf_counter();result=subprocess.run([str(args.checker),str(mesh)],capture_output=True,text=True,timeout=120)
            rows.append(dict(item,elapsed_ms=(perf_counter()-start)*1000,returncode=result.returncode,
                             stdout=result.stdout,stderr=result.stderr,
                             embedding=json.loads(result.stdout) if result.returncode==0 else None))
            mesh.unlink()
    report={'time_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'package_sha256':sha(args.package),'plan':plan,'checker':str(args.checker),'checker_sha256':sha(args.checker),
            'auditor_sha256':sha(Path(__file__)),'rows':rows,'status':'completed'}
    (args.root/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'objects':len(rows),'embedded_closed':sum(bool(r['embedding'] and r['embedding'].get('embedded_closed')) for r in rows)}))


if __name__=='__main__':main()
