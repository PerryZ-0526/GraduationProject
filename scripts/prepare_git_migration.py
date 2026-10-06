"""集中保存未入Git的实验产物，生成提交清单和换机恢复清单。"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


CODE = {'.py', '.cpp', '.c', '.h', '.hpp', '.hh', '.cc', '.cu', '.cuh',
        '.cmake', '.sh', '.ps1', '.bat', '.cmd', '.toml', '.yaml', '.yml',
        '.ini', '.cfg', '.robot', '.in', '.f', '.f90', '.make'}
DOCS = {'.md', '.rst', '.pdf', '.docx', '.pptx', '.png', '.jpg', '.jpeg',
        '.svg', '.html', '.css', '.js', '.ts', '.tex', '.bib'}
LIGHT = {'.json', '.txt', '.csv', '.log', '.tsv'}
NAMES = {'CMakeLists.txt', 'Makefile', 'LICENSE', 'COPYING', 'NOTICE',
         '.gitignore', '.gitattributes'}
SKIP_PARTS = {'.venv', '.idea', '__pycache__', '.pytest_cache', '.ruff_cache', '.worktrees'}
BEIJING = timezone(timedelta(hours=8))


def now():
    return datetime.now(BEIJING).isoformat(timespec='seconds')


def write_json(path, data):
    # 状态原子替换，避免迁移中断留下看似完成的半份回执。
    temp = path.with_suffix(path.suffix + '.part')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def git(root, *args):
    result = subprocess.run(['git', '-c', 'core.quotepath=false', *args], cwd=root,
                            capture_output=True, check=True)
    if result.stderr:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
    return result.stdout


def is_private(path):
    return (path.name.startswith('.env') and path.name != '.env.example'
            or path.name in {'.ssh_known_hosts', 'id_rsa', 'id_ed25519'}
            or path.suffix.lower() in {'.pem', '.key'})


def keep_in_git(path, size):
    if any(part in {'objects', 'refs', '.git'} for part in path.parts):
        return False
    if path.name.startswith('~$'):
        return False
    ext = path.suffix.lower()
    return (ext in CODE or ext in DOCS and size <= 10 * 1024**2
            or ext in LIGHT and size <= 256 * 1024 or path.name in NAMES)


def secret_matches(path):
    # 仅报告文件和行号，不把疑似口令内容写入控制台或回执。
    if path.suffix.lower() not in CODE | LIGHT | {'.md', '.rst', '.html', '.js', '.ts', '.patch', '.diff'}:
        return []
    text = path.read_text(encoding='utf-8', errors='replace')
    # 同时覆盖Python赋值和JSON键后的引号，避免漏掉结构化配置里的明文口令。
    pattern = re.compile(r'''(?i)(?:password|passwd|api_key|access_token)["']?\s*[=:]\s*["']([^"'\n]{4,})["']''')
    allowed = {'password', 'passwd', 'test', 'secret', 'example', 'changeme', 'your_password', 'none'}
    matches = []
    for match in pattern.finditer(text):
        value = match.group(1).strip()
        if value.lower() in allowed or any(token in value for token in ['{', '}', '<', '>', '${']):
            continue
        matches.append(text.count('\n', 0, match.start()) + 1)
    return matches


def make_plan(root, bundle, asset_source=None):
    # 用集合判定来源，避免数万文件逐次扫描整份路径列表。
    untracked = set(git(root, 'ls-files', '--others', '--exclude-standard', '-z').decode('utf-8').split('\0'))
    ignored = set(git(root, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z').decode('utf-8').split('\0'))
    changed = set(git(root, 'diff', '--name-only', '--diff-filter=ACMRT', '-z').decode('utf-8').split('\0'))
    stage = set()
    rows = []
    private = []
    findings = []
    for rel in sorted((untracked | ignored | changed) - {''}):
        path = Path(rel)
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if is_private(path):
            private.append(rel)
            continue
        source = root / path
        if source.is_dir():
            # 子模块指针单独核查，目录本身不能按普通文件复制。
            continue
        stat = source.stat()
        keep = rel in changed or rel in untracked and keep_in_git(path, stat.st_size)
        if keep:
            lines = secret_matches(source)
            if lines:
                findings.append({'path': rel, 'lines': lines})
            stage.add(rel)
        else:
            rows.append({'relative_path': rel, 'bytes': stat.st_size,
                         'mtime_ns': stat.st_mtime_ns, 'origin': 'ignored' if rel in ignored else 'untracked'})
    plan = {'time_beijing': now(), 'project_root': str(root), 'bundle_root': str(bundle),
            'stage_paths': sorted(stage), 'raw_files': rows, 'excluded_private_paths': private,
            'secret_review_findings': findings, 'raw_bytes': sum(row['bytes'] for row in rows)}
    write_json(bundle / '02-项目提交与原始数据迁移计划.json', plan)
    if asset_source:
        # 原D盘实验资产先固定完整清单，仅排除可重建缓存，不按日期丢弃负结果。
        asset_rows = []
        omitted = []
        errors = []
        def walk_error(error):
            errors.append(str(error))
        for base, dirs, files in os.walk(asset_source, onerror=walk_error):
            for name in files:
                source = Path(base, name)
                rel = source.relative_to(asset_source)
                stat = source.stat()
                row = {'relative_path': rel.as_posix(), 'bytes': stat.st_size,
                       'mtime_ns': stat.st_mtime_ns, 'origin': 'original_D_assets'}
                if any(part in {'__pycache__', '.pytest_cache', '.ruff_cache'} for part in rel.parts) or source.suffix in {'.pyc', '.pyo'}:
                    omitted.append(dict(row, reason='rebuildable_cache'))
                else:
                    asset_rows.append(row)
        if errors:
            raise RuntimeError('原D盘资产规划存在访问失败：' + repr(errors))
        asset_plan = {'time_beijing': now(), 'source_root': str(asset_source), 'raw_files': asset_rows,
                      'raw_bytes': sum(row['bytes'] for row in asset_rows), 'excluded_cache_files': omitted}
        write_json(bundle / '07-原D盘资产完整复制计划.json', asset_plan)
        print(json.dumps({'phase': 'asset_plan', 'files': len(asset_rows), 'bytes': asset_plan['raw_bytes'],
                          'excluded_cache_files': len(omitted)}, ensure_ascii=False), flush=True)
    print(json.dumps({'phase': 'plan', 'git_files': len(stage), 'raw_files': len(rows),
                      'raw_bytes': plan['raw_bytes'], 'secret_findings': findings[:30],
                      'secret_finding_count': len(findings)}, ensure_ascii=False), flush=True)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def copy_raw(root, bundle, assets=False):
    plan_path = bundle / ('07-原D盘资产完整复制计划.json' if assets else '02-项目提交与原始数据迁移计划.json')
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if assets:
        root = Path(plan['source_root'])
    else:
        assert Path(plan['project_root']) == root
    target = bundle / ('原D盘资产' if assets else '项目未入Git原始数据')
    target.mkdir(exist_ok=True)
    manifest = bundle / ('08-原D盘资产逐文件复制核对.jsonl' if assets else '03-项目原始数据逐文件复制核对.jsonl')
    completed = {}
    if manifest.exists():
        for line in manifest.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            completed[row['relative_path']] = row
    receipt_path = bundle / ('09-原D盘资产复制回执.json' if assets else '04-项目原始数据复制回执.json')
    state = {'status': 'running', 'kind': 'D_assets' if assets else 'project_raw', 'started_beijing': now(), 'planned_files': len(plan['raw_files']),
             'planned_bytes': plan['raw_bytes'], 'completed_files': len(completed),
             'completed_bytes': sum(row['bytes'] for row in completed.values()), 'errors': []}
    write_json(receipt_path, state)
    last_report = time.monotonic()
    try:
        with manifest.open('a', encoding='utf-8') as output:
            for row in plan['raw_files']:
                rel = row['relative_path']
                source = root / rel
                destination = target / rel
                if rel in completed:
                    assert destination.stat().st_size == row['bytes']
                    assert digest(destination) == completed[rel]['sha256']
                    continue
                before = source.stat()
                if before.st_size != row['bytes'] or before.st_mtime_ns != row['mtime_ns']:
                    raise RuntimeError('源文件自规划后发生变化：' + rel)
                destination.parent.mkdir(parents=True, exist_ok=True)
                temp = destination.with_name(destination.name + '.migration-part')
                sha = hashlib.sha256()
                with source.open('rb') as src, temp.open('wb') as dst:
                    for block in iter(lambda: src.read(4 * 1024**2), b''):
                        sha.update(block)
                        dst.write(block)
                after = source.stat()
                if after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
                    raise RuntimeError('复制期间源文件变化：' + rel)
                if temp.stat().st_size != row['bytes'] or digest(temp) != sha.hexdigest():
                    raise RuntimeError('目标摘要不匹配：' + rel)
                shutil.copystat(source, temp)
                os.replace(temp, destination)
                saved = dict(row, sha256=sha.hexdigest(), time_beijing=now(), verified=True)
                output.write(json.dumps(saved, ensure_ascii=False) + '\n')
                output.flush()
                completed[rel] = saved
                state['completed_files'] += 1
                state['completed_bytes'] += row['bytes']
                if time.monotonic() - last_report >= 10:
                    state['updated_beijing'] = now()
                    write_json(receipt_path, state)
                    print(json.dumps(state, ensure_ascii=False), flush=True)
                    last_report = time.monotonic()
        state.update(status='completed', finished_beijing=now(), manifest_sha256=digest(manifest),
                     plan_sha256=digest(plan_path), originals_preserved=True)
        write_json(receipt_path, state)
        print(json.dumps(state, ensure_ascii=False), flush=True)
    except Exception as error:
        state.update(status='failed', updated_beijing=now())
        state['errors'].append(str(error))
        write_json(receipt_path, state)
        raise


def index_assets(bundle):
    # 同卷移动只改目录位置；原文件内容不变，清单诚实标明未再次全量求摘要。
    root = bundle / '原D盘资产'
    manifest = bundle / '05-原D盘资产逐文件位置清单.jsonl'
    totals = Counter()
    counts = Counter()
    errors = []
    with manifest.open('w', encoding='utf-8') as output:
        for base, dirs, files in os.walk(root, onerror=lambda error: errors.append(str(error))):
            for name in sorted(files):
                path = Path(base, name)
                rel = path.relative_to(root)
                stat = path.stat()
                counts[rel.parts[0]] += 1
                totals[rel.parts[0]] += stat.st_size
                output.write(json.dumps({'relative_path': rel.as_posix(), 'bytes': stat.st_size,
                                          'mtime_ns': stat.st_mtime_ns,
                                          'sha256_status': 'not_rehashed_same_volume_move'}, ensure_ascii=False) + '\n')
    receipt = {'status': 'completed' if not errors else 'failed', 'time_beijing': now(),
               'files': dict(counts), 'bytes': dict(totals), 'errors': errors,
               'manifest_sha256': digest(manifest), 'same_volume_move': True,
               'original_paths_preserved_by_junction': True}
    write_json(bundle / '06-原D盘资产整理回执.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--phase', choices=['plan', 'copy', 'assets', 'index'], required=True)
    parser.add_argument('--asset-source', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    bundle = args.bundle.resolve()
    # 最终迁移目录只允许位于用户明确指定的E盘位置或本次D盘中间整理目录。
    allowed_parent = Path('E:/实验数据迁移').resolve()
    assert bundle.is_dir() and (bundle.parent == allowed_parent or bundle.parent == Path('D:/'))
    if args.phase == 'plan':
        make_plan(root, bundle, args.asset_source.resolve() if args.asset_source else None)
    elif args.phase == 'copy':
        copy_raw(root, bundle)
    elif args.phase == 'assets':
        copy_raw(root, bundle, assets=True)
    else:
        index_assets(bundle)


if __name__ == '__main__':
    main()
