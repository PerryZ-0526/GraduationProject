"""只封存暂停时已准备的资产和控制器，不启动研究实验。"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import zipfile


BASE = Path(__file__).resolve().parent
PARENT = Path('D:/GraduationProject实验输出')
ROOT = PARENT/'20261007_批更新自适应认证与本机质量完整验证'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    frozen = json.loads((ROOT/'00-批更新与本机新质量方法冻结.json').read_text(encoding='utf-8'))
    for name, digest in frozen['files'].items():
        assert sha(ROOT/name) == digest, name
    assert not (ROOT/'long/03-完整批量父反馈记录.json').exists()
    assert not (ROOT/'live/03-完整批量父反馈记录.json').exists()
    files = {'prepared/'+p.relative_to(ROOT).as_posix():p for p in ROOT.rglob('*')
             if p.is_file() and not any(part in ('memory_build', '__pycache__') for part in p.parts)}
    for name in ('prepare_local_batch_certificate.py', 'prepare_local_long_certificate.py', 'prepare_local_live_queue.py',
                 'collect_local_long_certificate.py', 'archive_local_long_certificate.py', 'package_paused_quality_handoff.py'):
        files['controllers/'+name] = BASE/name
    manifest = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(), goal_status='paused',
                    execution_status='prepared_not_executed', planned_long_events=1536, planned_live_events=384,
                    members={name:dict(size=p.stat().st_size, sha256=sha(p)) for name, p in files.items()})
    target = PARENT/'20261007_暂停交接_批更新与新质量已准备资产.zip'
    assert not target.exists()
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
        archive.writestr('01-暂停时点完整资产清单.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    # 只做交接归档可读性核对，不执行算法、输入队列或GPU任务。
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist()) == set(files)|{'01-暂停时点完整资产清单.json'} and archive.testzip() is None
        for name, expected in manifest['members'].items():
            assert archive.getinfo(name).file_size == expected['size']
            with archive.open(name) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected['sha256']
    result = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(), goal_status='paused',
                  execution_status='prepared_not_executed', archive=str(target), size=target.stat().st_size,
                  sha256=sha(target), members=len(files)+1, all_member_sizes_sha256_crc_verified=True)
    receipt = BASE/'诊断证据/75-暂停交接已准备资产完整归档核对.json'
    assert not receipt.exists()
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
