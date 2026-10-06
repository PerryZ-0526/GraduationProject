"""封存完整原计划、实际数组和Arc队列，并逐成员核对，失败记录不删除。"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import zipfile


BASE = Path(__file__).resolve().parent
PARENT = Path('D:/GraduationProject实验输出')
ROOT = PARENT/'20261007_自适应方向认证本机完整长轨迹'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    summary = ROOT/'07-完整长反馈与实际队列联合汇总.json'
    assert json.loads(summary.read_text(encoding='utf-8'))['status'] == 'completed_with_recorded_failures'
    frozen = json.loads((ROOT/'00-完整长轨迹输入与本机方法冻结.json').read_text(encoding='utf-8'))
    for name, digest in frozen['files'].items():
        assert sha(ROOT/name) == digest, name
    binding = json.loads((ROOT/'01-常驻长序列运行绑定.json').read_text(encoding='utf-8'))
    for name, digest in binding['generated_entry_sha256'].items():
        assert sha(ROOT/'workers'/name) == digest, name
    prerequisite = PARENT/'20261007_自适应方向认证组件与完整反馈证据.zip'
    assert sha(prerequisite) == 'd0de55d0cc2c75f273c40cbd0903c36879b01e75a0ea348abcbff722dedfed43'
    files = {'experiment/'+p.relative_to(ROOT).as_posix():p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    for name in ('prepare_local_long_certificate.py', 'prepare_local_live_queue.py', 'collect_local_long_certificate.py', 'archive_local_long_certificate.py'):
        files['controllers/'+name] = BASE/name
    manifest = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                    members={name:dict(size=p.stat().st_size, sha256=sha(p)) for name, p in files.items()},
                    prerequisite=dict(path=str(prerequisite), sha256=sha(prerequisite)),
                    scope='实际本机执行源码、DLL、完整768输入及所有发布/拒绝/阻断、原数组和像素；编译依赖沿19号前提包恢复')
    target = PARENT/'20261007_本机完整长反馈与Arc真实队列证据.zip'
    assert not target.exists()
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
        archive.writestr('01-完整成员摘要清单.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    # 完整成员集合、大小、摘要及CRC逐件验证，不能只核对ZIP文件名。
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist()) == set(files)|{'01-完整成员摘要清单.json'} and archive.testzip() is None
        for name, expected in manifest['members'].items():
            assert archive.getinfo(name).file_size == expected['size']
            with archive.open(name) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected['sha256']
    receipt = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(), status='completed',
                   path=str(target), bytes=target.stat().st_size, sha256=sha(target), members=len(files)+1,
                   all_member_sizes_sha256_crc_verified=True, frozen_method_and_generated_entries_verified=True)
    (ROOT/'08-完整证据归档与成员核对.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
