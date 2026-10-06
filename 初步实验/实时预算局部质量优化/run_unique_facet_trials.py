"""控制及保存对象对应通过后，交错执行唯一面扫描四预算CUDA反馈与真实像素。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path('/tmp/geogram_unique_facets_20261006_flat')
WORKERS = ROOT / 'workers'
CT = '/tmp/geogram_certified_pairs_20261006_r3/inputs/ct_record.json'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


controls = json.loads((ROOT/'cleanup_controls_v2_parsed.json').read_text())
assert len(controls['cases']) == 12 and all(case['identical'] and case['pairs'] == 21 for case in controls['cases'])
audited = ROOT/'static_pairs/02-保存对象全量复审与有界几何对应.json'
audit = json.loads(audited.read_text(encoding='utf-8'))
assert audit['status'] == 'completed' and audit['correspondence_proved'] == 162 and audit['saved_objects'] == 324
assert json.loads((ROOT/'static_pairs/01-唯一面扫描同源完整对照.json').read_text())['all_checks_identical']
# 只给本批独立工作器增加显式参数；既有冻结运行目录不变。
feedback = WORKERS/'verified_budget_feedback.py'
text = feedback.read_text(encoding='utf-8')
anchor = "    p.add_argument('--certified-operand-pairs',action='store_true')"
assert text.count(anchor) == 1
text = text.replace(anchor, anchor+"\n    # 唯一面完整扫描可单独开关，与输入认证选择分开记录。\n    p.add_argument('--linear-unique-facets',action='store_true')")
anchor = "    report['certified_operand_pairs']=args.certified_operand_pairs"
assert text.count(anchor) == 1
text = text.replace(anchor, anchor+"\n    report['linear_unique_facets']=args.linear_unique_facets")
anchor = 'no_simplify=True,certified_operands=args.certified_operand_pairs)'
assert text.count(anchor) == 1
text = text.replace(anchor, 'no_simplify=True,certified_operands=args.certified_operand_pairs,linear_unique_facets=args.linear_unique_facets)')
feedback.write_text(text, encoding='utf-8')
render = WORKERS/'render_live_gpu_feedback.py'
text = render.read_text(encoding='utf-8')
anchor = 'args=p.parse_args();'
assert text.count(anchor) == 1
text = text.replace(anchor, "p.add_argument('--linear-unique-facets',action='store_true');"+anchor)
anchor = '    feedback(publisher=publish)'
assert text.count(anchor) == 1
text = text.replace(anchor, "    # 像素批次沿用同一候选开关，不悄悄切回排序基线。\n    if args.linear_unique_facets:sys.argv.append('--linear-unique-facets')\n"+anchor)
render.write_text(text, encoding='utf-8')
record = ROOT/'03-唯一面扫描完整CUDA四预算反馈执行记录.json'
assert not record.exists()
report = {'time_beijing': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
          'status': 'running', 'control_audit_sha256': sha(audited), 'stages': [], 'trials': [], 'renders': [],
          'gpu_shared': True, 'planned_feedback_events': 384,
          'frozen_workers': {path.name: sha(path) for path in WORKERS.iterdir() if path.suffix in ('.py','.cpp','.so','.json')},
          'build_identity': json.loads((WORKERS/'build_identity.json').read_text())}
env = dict(os.environ, LD_PRELOAD='/usr/lib/x86_64-linux-gnu/libstdc++.so.6')


def save():
    temporary = record.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(record)


def execute(name, argv, environment=env):
    for member, digest in report['frozen_workers'].items():
        assert sha(WORKERS/member) == digest
    with (ROOT/(name+'.log')).open('x', encoding='utf-8') as stream:
        code = subprocess.run(argv, cwd=WORKERS, env=environment, stdout=stream, stderr=subprocess.STDOUT).returncode
    report['stages'].append({'name': name, 'argv': argv, 'returncode': code})
    save()
    assert code == 0, name


save()
try:
    for repeat in range(3):
        for enabled in ([False,True] if repeat%2 == 0 else [True,False]):
            label = 'flat' if enabled else 'original'
            out = ROOT/f'r{repeat}_{label}'
            trial = {'repeat': repeat, 'linear_unique_facets': enabled, 'status': 'running', 'output': str(out)}
            report['trials'].append(trial)
            save()
            argv = [sys.executable, str(feedback), '--ct-record', CT, '--output', str(out),
                    '--fixed-flip-certificate', '--early-quality-return', '--edge-backend', 'cuda', '--certified-operand-pairs']
            if enabled:argv.append('--linear-unique-facets')
            execute(f'feedback_{repeat}_{label}', argv)
            execute(f'audit_{repeat}_{label}', [sys.executable, str(WORKERS/'audit_verified_budget_feedback.py'), '--root', str(out)])
            trial.update(status='completed', record_sha256=sha(out/'01-真实父反馈四预算完整记录.json'),
                         audit_sha256=sha(out/'02-完整保存全量精确复审与四预算统计.json'))
            save()
    runtime = Path('/tmp/compact_short_repair_20261006/render_trials_retry2')
    render_env = dict(env, PYTHONPATH=str(runtime/'python_deps'),
                      LD_LIBRARY_PATH=str(runtime/'egl/usr/lib/x86_64-linux-gnu')+':'+env.get('LD_LIBRARY_PATH',''),
                      VTK_DEFAULT_OPENGL_WINDOW='vtkEGLRenderWindow')
    for enabled, budget in [(False,100),(True,100),(True,200)]:
        label = 'flat' if enabled else 'original'
        out = ROOT/f'render_{label}_{budget}'
        argv = [sys.executable, str(render), '--ct-record', CT, '--output', str(out), '--budget', str(budget)]
        if enabled:argv.append('--linear-unique-facets')
        execute(f'render_{label}_{budget}', argv, render_env)
        report['renders'].append({'linear_unique_facets': enabled, 'budget_ms': budget,
                                 'record': str(out/'01-真实GPU父反馈与像素交付完整记录.json'),
                                 'sha256': sha(out/'01-真实GPU父反馈与像素交付完整记录.json')})
        save()
    report['status'] = 'completed'
    save()
except Exception as error:
    report.update(status='failed', error=repr(error))
    save()
    raise
