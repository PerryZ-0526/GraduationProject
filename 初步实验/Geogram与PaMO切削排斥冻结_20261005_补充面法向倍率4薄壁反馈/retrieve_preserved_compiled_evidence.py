"""只读取同次完整投影实际编译副本，核对变换与混合核体，不重跑GPU。"""
import argparse
from pathlib import Path
from run_constrained_batch import RemoteQuality
from run_geometry_study import retrieve,save,now
from audit_followup_candidate import sha256
from preserved_collision_source import preserve_energy_source,preserve_ccd_source


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args = parser.parse_args()
    folder = args.folder/"compiled_evidence"
    folder.mkdir(exist_ok=False)
    engine = RemoteQuality(args.folder,args.port)
    try:
        pairs = [("author_precision_snapshots/collision_gradient_precision.py","preserved_geometry_snapshots/preserved_collision_energy.py",preserve_energy_source),
                 ("author_precision_snapshots/ccd_kernels_precision.py","preserved_geometry_snapshots/preserved_ccd.py",preserve_ccd_source)]
        rows = []
        for original,modified,transform in pairs:
            for path in (original,modified):
                retrieve(engine.client,engine.sftp,engine.remote+"/"+path,folder/Path(path).name)
            old,new = folder/Path(original).name,folder/Path(modified).name
            expected = transform(old.read_text(encoding="utf-8"))
            actual = new.read_text(encoding="utf-8")
            if expected != actual:
                raise ValueError("实际编译副本与登记分支变换不一致")
            rows.append(dict(original=old.name,modified=new.name,original_sha256=sha256(old),modified_sha256=sha256(new),transform_matches=True))
        retrieve(engine.client,engine.sftp,engine.remote+"/preserved_install.json",folder/"preserved_install.json")
        save(folder/"01-实际编译分支绑定.json",dict(time_beijing=now(),rows=rows,published=False,scope="同次远端编译源绑定，不新执行GPU"))
        print("compiled source pairs",len(rows))
    finally:
        engine.close()
