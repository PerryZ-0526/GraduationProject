"""复用明确的独立质量和距离口径，只绑定新版本实际输出。"""
from pathlib import Path

here = Path(__file__).resolve().parent
code = (here / '122-有界邻域生成全部重复质量几何速度复算.py').read_text('utf8')
code = code.replace('第七轮原生全部重复与诊断输出', '第十轮种子组原生全部重复与诊断输出')
code = code.replace('123-有界邻域生成原生十一同输入完整复算.json', '170-种子组原生十一同输入完整复算.json')
path = here / '169-种子组全部重复质量几何速度复算.py'
assert not path.exists()
path.write_text(code, 'utf8')
print('prepared_independent_154_output_recomputation')
