"""固定数值快照顺序执行六家族18事件，每路线终态后独立保存复审。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main():
    project = Path.cwd()
    root = Path('D:/GraduationProject_切削排斥证据')
    snapshot = project / '初步实验/Geogram与PaMO切削排斥冻结_20261005_补充面法向倍率4薄壁反馈'
    manifest = snapshot / '01-执行源码冻结清单.json'
    for row in json.loads(manifest.read_text('utf8')):
        if hashlib.sha256((snapshot / row['file']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('冻结入口或数值依赖改变')
    prepared = root / '可复用磨削测试集/两档切削排斥新参数七家族_v28'
    pm = json.loads((prepared / '01-完整范围冻结清单.json').read_text('utf8'))
    routes = [r for r in pm['routes'] if not r['id'].startswith('薄壁_')]
    output = root / '20261005_补充面法向倍率4六家族18事件完整开发'
    output.mkdir(exist_ok=False)
    launcher = Path(__file__).with_name('frozen_feedback_child.py')
    audit = project / '初步实验/Geogram与PaMO切削排斥冻结_20261005_补充支撑独立保存复审'
    side = project / '初步实验/Geogram与PaMO组合验证/实验结果/20261004_切削排斥精确材料侧分类开发'
    build = project / '初步实验/Geogram与PaMO组合验证/实验结果/20261004_简化邻接顺序隔离构建/01-简化邻接顺序隔离构建.json'
    report = {'生成时间': now(), '修改时间及修改内容': '首次生成，六路线先冻结执行分母',
              '文档概述': '已见六家族开发，不含已完成薄壁，与本轮薄壁相同补充支撑方向、倍率4及最低R256数值快照',
              '索引目录': ['planned_routes', 'rows', 'summary'], 'status': 'running',
              'snapshot_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
              'planned_routes': [{'route': r['id'], 'events': r['cutting_prefix_ids']} for r in routes],
              'planned_events': sum(len(r['cutting_prefix_ids']) for r in routes), 'rows': []}
    record = output / '01-六家族完整执行与独立复审记录.json'

    def save():
        record.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')

    save()
    for route in routes:
        rid = route['id']
        batch = output / rid
        qa = output / (rid + '_保存复审')
        row = {'route': rid, 'planned_events': len(route['cutting_prefix_ids']), 'status': 'running'}
        report['rows'].append(row)
        save()
        print(rid, 'started', flush=True)
        # 每路线使用独立本机进程与独立远端目录，顺序GPU求解避免显存争用。
        args = ['--prepared', str(prepared), '--reference-batch', str(root / '20261005_两档新参数七家族独立参照生成' / rid),
                '--side-validation', str(side), '--output', str(batch), '--port', '51667', '--route', rid,
                '--build-record', str(build), '--offset-factor', '0.0']
        row['returncode'] = subprocess.run([sys.executable, str(launcher), str(snapshot), str(snapshot / 'run_completed_support_feedback.py')] + args).returncode
        terminal = batch / '01-统一配置完整父反馈记录.json'
        if terminal.exists():
            child = json.loads(terminal.read_text('utf8'))
            row['batch_sha256'] = hashlib.sha256(terminal.read_bytes()).hexdigest()
            row['batch_status'] = child['status']
            row['outcomes'] = [{'event': r['event'], 'status': r['status']} for r in child['rows']]
            row['summary'] = child.get('summary')
        # 只审计已达到完整终态的保存输出，异常保留，不编造缺失事件成功。
        if row.get('batch_status') == 'completed_with_recorded_outcomes':
            args = ['--prepared', str(prepared), '--batch', str(batch), '--source-batch', str(batch), '--side-validation', str(side),
                    '--output', str(qa), '--kind', 'unified']
            row['audit_returncode'] = subprocess.run([sys.executable, str(launcher), str(audit), str(audit / 'audit_completed_support_outputs.py')] + args).returncode
            q = qa / '01-保存候选整面与材料侧独立复审.json'
            if q.exists():
                row['audit_sha256'] = hashlib.sha256(q.read_bytes()).hexdigest()
                row['audit_summary'] = json.loads(q.read_text('utf8'))['summary']
        row['status'] = 'terminal'
        save()
        print(rid, 'terminal', row.get('summary'), flush=True)
    report.update(status='completed_with_recorded_outcomes', finished_beijing=now(),
                  summary={'planned_events': report['planned_events'], 'published': sum((r.get('summary') or {}).get('published', 0) for r in report['rows']),
                           'whole_routes': sum((r.get('summary') or {}).get('whole_route_complete', False) for r in report['rows']),
                           'routes': len(routes), 'process_failures': sum(r['returncode'] != 0 for r in report['rows']),
                           'saved_passed': sum((r.get('audit_summary') or {}).get('passed', 0) for r in report['rows'])})
    save()
    print(report['summary'], flush=True)


if __name__ == '__main__':
    main()
