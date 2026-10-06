"""完整生成终态后顺序执行已冻结复审，保留每项独立日志和返回状态。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import subprocess
import sys


def digest(path):
    """绑定真实文件字节，复审之间持续核对生成终态未变。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    """所有执行记录采用北京时间。"""
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


here = Path(__file__).parent
study = Path('D:/GraduationProject_切削排斥证据/20261006_Geogram共享边竞争生成真实CT连续验证')
protocol_path = study/'06-连续六项终态复审运行前冻结清单.json'
protocol = json.loads(protocol_path.read_text('utf8'))
assert protocol['status'] == 'prepared_six_terminal_auditors_syntax_and_hashes_verified'
mp = study/'43-共享边竞争生成真实CT十六刀冻结清单.json'
assert digest(mp) == protocol['generation_manifest_sha256']
manifest = json.loads(mp.read_text('utf8'))
for path, expected in manifest['modules'].items():
    assert digest(Path(path)) == expected
rp = study/'真实CT完整父反馈结果/01-真实CT十六刀完整父反馈记录.json'
record = json.loads(rp.read_text('utf8'))
assert record['status'] == 'completed_with_recorded_outcomes' and 'current_execution' not in record
assert len(record['routes']) == 1 and len(record['routes'][0]['events']) == len(manifest['tools']) == 16
assert record['manifest_sha256'] == digest(mp)
source_hash = digest(rp)
entries = [
    ('31-有界骨面保存对象与实际父链复审.py', '保存复审与父链核对/01-真实CT保存复审与完整父链记录.json',
     'completed_with_verified_outputs_and_parent_chains', 'prior_sha256'),
    ('30-连续有界翻边准确证书与预算账本复审.py', '连续有界翻边保存证书与账本复审/01-连续有界翻边准确证书与预算账本复审.json',
     'completed_with_continuous_bone_certificates_and_ledger_verified', 'prior_record_sha256'),
    ('21-连续来源阶段精确零面与收缩证书复审.py', '完整父反馈精确零面与来源证书复审/01-十六事件精确零面与来源保存证书复审.json',
     'completed_with_all_events_zero_images_and_source_certificates_verified', 'source_record_sha256'),
    ('44-连续全部实际策略与选择账本独立复审.py', '连续全部策略选择与表面账本复审/01-十六事件全部实际策略选择与表面账本复审.json',
     'completed_all_sixteen_events_all_actual_strategies_selection_and_ledger_verified', 'source_record_sha256'),
    ('22-有界骨面连续父链累计参照分布.py', '新父链对独立累计参照分布/01-新父链十六事件独立累计参照分布.json',
     'completed_with_matched_initial_tools_and_cumulative_distributions', 'candidate_record_sha256'),
    ('45-连续工具邻域与同源质量成本完整复算.py', '连续同源收益工具邻域与成本复算/01-十六事件同源收益与路线质量成本完整复算.json',
     'completed_sixteen_event_same_input_and_route_quality_cost_recomputed', 'source_record_sha256')]
assert [str(study/e[0]) for e in entries] == [r['path'] for r in protocol['rows']]
for frozen in protocol['rows']:
    assert digest(Path(frozen['path'])) == frozen['sha256']
bootstrap = Path('初步实验/Geogram与PaMO切削排斥冻结_20261005_原始顶点提案六家族执行控制/frozen_feedback_child.py').resolve()
snapshot = Path('初步实验/Geogram与PaMO切削排斥冻结_20261006_实际输出局部表示六刀兼容连续开发').resolve()
receipt_path = here/'04-连续终态六项复审顺序执行记录.json'
assert not receipt_path.exists()
receipt = {'生成时间': now(), '修改时间及修改内容': '首次执行本轮完整生成终态的六项独立复审',
    '文档概述': '所有实际策略、父链、来源、骨面账本、累计分布与成本分别核对，不重跑几何生成',
    '索引目录': ['rows'], 'status': 'running', 'source_record_sha256': source_hash,
    'protocol_sha256': digest(protocol_path), 'coordinator_sha256': digest(Path(__file__)),
    'GPU_calls': 0, 'new_generation_calls': 0, 'rows': []}


def save_receipt():
    """每项启动和终止单独记录，不能用总体运行字段推断子项通过。"""
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', 'utf8')


save_receipt()
try:
    for index, ((entry, output, status, binding), frozen) in enumerate(zip(entries, protocol['rows'])):
        path = study/entry
        assert digest(rp) == source_hash and digest(path) == frozen['sha256']
        assert not (study/output).exists()
        log = here/f'{index+5:02d}-{entry[:-3]}执行日志.txt'
        row = {'entry': str(path), 'entry_sha256': digest(path), 'output_path': str(study/output),
            'log_path': str(log), 'status': 'executing', 'started_beijing': now()}
        receipt['rows'].append(row)
        save_receipt()
        print('启动终态复审', entry, flush=True)
        with log.open('x', encoding='utf8') as stream:
            response = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(bootstrap), str(snapshot), str(path)],
                stdout=stream, stderr=subprocess.STDOUT)
        row.update(returncode=response.returncode, finished_beijing=now(), log_sha256=digest(log))
        assert response.returncode == 0, f'复审入口非零退出：{entry}，日志保留'
        saved = json.loads((study/output).read_text('utf8'))
        assert saved['status'] == status and saved[binding] == source_hash
        assert digest(rp) == source_hash
        row.update(status='completed_verified_bound_terminal_audit', output_sha256=digest(study/output),
            audit_terminal_status=saved['status'])
        save_receipt()
        print('终态复审完成', entry, flush=True)
    receipt.update(status='completed_all_six_bound_terminal_audits', finished_beijing=now())
    save_receipt()
except Exception as error:
    # 已退出或绑定失败的当前子项明确终止，不能留下执行中状态误导后续恢复。
    if receipt['rows'] and receipt['rows'][-1]['status'] == 'executing':
        receipt['rows'][-1].update(status='failed_execution_or_terminal_binding', finished_beijing=now())
    receipt.update(status='failed_with_preserved_prior_audits_and_logs', reason=str(error), finished_beijing=now())
    save_receipt()
    raise
