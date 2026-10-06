"""完整长反馈终态后，冻结本机真实生产队列与Intel Arc像素入口。"""
import hashlib
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent
ROOT = Path('D:/GraduationProject实验输出/20261007_自适应方向认证本机完整长轨迹')
SOURCE = BASE.parent/'连续磨削实验基座/resident_live_queue_worker.py'


def main():
    report = json.loads((ROOT/'02-常驻长序列完整记录.json').read_text(encoding='utf-8'))
    assert report['status'] in ('completed', 'completed_with_recorded_failures')
    assert len(report['runs']) == 4 and all(run['planned'] == 384 for run in report['runs'])
    text = SOURCE.read_text(encoding='utf-8')
    # 仅切换本机后端和显示身份；保留原工具顺序、失败阻断及实际入队计时。
    text = text.replace('NVIDIA', 'Intel Arc')
    text = text.replace("'--edge-backend','cuda','--certified-operand-pairs'", "'--edge-backend','cpu','--certified-operand-pairs','--linear-unique-facets'")
    text = text.replace('.read_text())', ".read_text(encoding='utf-8'))")
    text = text.replace("if 'Intel Arc' not in capabilities:", "if 'Intel' not in capabilities or 'Arc' not in capabilities:")
    # 完成与拒绝分开登记，不能把全程完成写成失败，也不能漏掉未执行分母。
    text = text.replace("report.update(status='completed_with_recorded_rejections',finished_beijing=now())",
                        "report.update(status='completed_with_recorded_rejections' if any(run['first_rejection'] is not None for run in runs) else 'completed',finished_beijing=now())")
    target = ROOT/'resident_local_live_queue.py'
    assert not target.exists()
    target.write_text(text, encoding='utf-8')
    record = dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  actual_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), planned_per_rate=384,
                  rates_hz=[5], hardware='本机CPU维护与Intel Arc离屏像素', input_preloaded=True,
                  timing='实际入队至数组及实际像素；包括排队和首次冷渲染，启动输入认证单列')
    (ROOT/'06-本机真实队列入口冻结.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='prepared', planned_events=384), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
