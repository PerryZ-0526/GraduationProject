"""准备同配置评价，超长原生调用记录为失败，不补写为成功输出。"""
from pathlib import Path

here = Path(__file__).resolve().parent
worker = (here / '132-内部改善保留原生交错评价与诊断.py').read_text('utf8').replace('第八轮', '第十轮')
anchor = 'save()\nrng=random.Random'
replacement = '''def native_run(args, **kwargs):
    """限制研究批次的单次运行；到期保留实际部分日志并明确记录失败。"""
    try:
        return subprocess.run(args, timeout=30, **kwargs)
    except subprocess.TimeoutExpired as error:
        partial = error.stdout or ''
        if isinstance(partial, bytes): partial = partial.decode('utf8', errors='replace')
        return subprocess.CompletedProcess(args, 124, partial + '\\nNATIVE_RESEARCH_TIMEOUT seconds=30\\n')


record['planned_native_benchmark_attempts'] = 154
record['native_call_operational_timeout_seconds'] = 30
record['timeout_semantics'] = '到期是本候选执行失败，不算成功输出或质量收益，不重启旧调用'
save()
rng=random.Random'''
assert worker.count(anchor) == 1
worker = worker.replace(anchor, replacement)
worker = worker.replace('process=subprocess.run([str(root/method)', 'process=native_run([str(root/method)')
worker = worker.replace("p=subprocess.run([str(root/'candidate')", "p=native_run([str(root/'candidate')")
worker_path = here / '161-种子组原生交错评价与有界执行.py'
assert not worker_path.exists()
worker_path.write_text(worker, 'utf8')
controller = (here / '133-内部改善保留实际评价上传执行取回.py').read_text('utf8')
for before, after in [('第八轮', '第十轮'), ('20261006_09', '20261006_11'),
                      ('132-内部改善保留原生交错评价与诊断.py', worker_path.name),
                      ('130-内部改善保留实际原生编译记录.json', '159-种子分组与边界一致实际原生编译记录.json'),
                      ('125-差面边界触发与内部改善保留源码清单.json', '154-种子分组与边界一致生成源码清单.json'),
                      ('134-内部改善保留原生评价执行取回记录.json', '163-种子组原生评价执行取回记录.json'),
                      ('135-内部改善保留完整评价控制台日志.txt', '164-种子组原生完整评价控制台日志.txt'),
                      ('136-内部改善保留全部重复与诊断输出.zip', '165-种子组原生全部重复与诊断输出.zip'),
                      ('第十轮原生全部重复与诊断输出', '第十轮种子组原生全部重复与诊断输出')]:
    controller = controller.replace(before, after)
path = here / '162-种子组原生评价上传执行取回.py'
assert not path.exists()
path.write_text(controller, 'utf8')
print('prepared_native_evaluation_with_recorded_30_second_failure_limit')
