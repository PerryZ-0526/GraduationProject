"""核对既有旧批次保存对象，减少跨网络重复复制。"""
from pathlib import Path
import hashlib
import json

roots = [Path('D:/GraduationProject实验输出') / name for name in [
    '20261005_原活动面限定完整154事件反馈',
    '20261005_候选与独立参照同物理清理完整154事件反馈',
    '20261005_清理顺序修复与初态锚点完整154事件反馈',
    '20261005_物理面积完整154事件反馈']]
roots.append(Path(__file__).resolve().parents[2] / 'Geogram与PaMO组合验证/实验结果/20261004_追加锚点完整能量真实反馈')
result = []
for root in roots:
    entries = {}
    for p in sorted(root.rglob('*')):
        if not p.is_file():
            continue
        with p.open('rb') as stream:
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        entries[p.relative_to(root).as_posix()] = {'size': p.stat().st_size, 'sha256': sha}
    result.append({'local_root': str(root), 'files': entries})
    print(json.dumps({'root': str(root), 'files': len(entries)}, ensure_ascii=False), flush=True)
out = Path(__file__).parent / '18-本机既有五批文件摘要.json'
assert not out.exists()
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
