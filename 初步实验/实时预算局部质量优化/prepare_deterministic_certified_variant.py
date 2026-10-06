"""另建确定性约束插入版本，保留首版候选及其严格对拍失败现场。"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base, root = args.baseline.resolve(), args.output.resolve()
    assert root.parent == base.parent and root != base
    root.mkdir(exist_ok=False)
    sha = lambda data: hashlib.sha256(data).hexdigest()
    for name in ['opennl.zip', 'amgcl.zip', 'libmeshb.zip', 'rply.zip']:
        shutil.copyfile(base / name, root / name)
    member = 'src/lib/geogram/mesh/mesh_surface_intersection.cpp'
    with zipfile.ZipFile(base / 'geogram.zip') as archive:
        original = archive.read(member)
        text = original.decode()
        before = 'return (a.f1 < b.f1);'
        assert text.count(before) == 1
        after = '''// 认证模式固定同一原面内部的约束插入次序，避免并行到达顺序影响细小面三角化。
                    if(CmdLine::arg_is_declared("algo:certified_operands") &&
                       CmdLine::get_arg_bool("algo:certified_operands")) {
                        return std::tie(a.f1,a.f2,a.A_rgn_f1,a.A_rgn_f2,a.B_rgn_f1,a.B_rgn_f2) <
                               std::tie(b.f1,b.f2,b.A_rgn_f1,b.A_rgn_f2,b.B_rgn_f1,b.B_rgn_f2);
                    }
                    // 默认路径继续使用作者原排序，原版对照不受候选规则影响。
                    return (a.f1 < b.f1);'''
        text = text.replace(before, after).replace('#include <sstream>', '#include <tuple>\n#include <sstream>', 1)
        changed = text.encode()
        with zipfile.ZipFile(root / 'geogram.zip', 'x', zipfile.ZIP_DEFLATED) as output:
            for info in archive.infolist():
                output.writestr(info, changed if info.filename == member else archive.read(info))
    rows = []
    with zipfile.ZipFile(base / 'workers.zip') as archive:
        with zipfile.ZipFile(root / 'workers.zip', 'x', zipfile.ZIP_DEFLATED) as output:
            for info in archive.infolist():
                if info.filename == 'manifest.json':
                    continue
                data = archive.read(info)
                if info.filename == 'inputs/ct_record.json':
                    # 只重绑定新私有路径，不改初态、工具字节或事件分母。
                    record = json.loads(data)
                    for event in record['routes'][0]['events']:
                        event['tool_path'] = str(root / 'inputs' / Path(event['tool_path']).name)
                    record['routes'][0]['events'][0]['parent_path'] = str(root / 'inputs/initial.obj')
                    data = json.dumps(record, ensure_ascii=False, indent=2).encode()
                output.writestr(info.filename, data)
                rows.append(dict(name=info.filename, size=len(data), sha256=sha(data)))
            output.writestr('manifest.json', json.dumps(rows, ensure_ascii=False, indent=2))
    shutil.copyfile(base / 'build_linux_runtime.py', root / 'build_linux_runtime.py')
    record = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                  status='prepared_not_validated', original_sha256=sha(original), candidate_sha256=sha(changed),
                  geogram_archive_sha256=sha((root / 'geogram.zip').read_bytes()),
                  worker_archive_sha256=sha((root / 'workers.zip').read_bytes()),
                  scope='独立新构建；只在认证候选路径固定约束次序；严格结果对拍仍需执行')
    (root / '01-确定性约束候选源码准备.json').write_text(json.dumps(record, ensure_ascii=False, indent=2))
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
