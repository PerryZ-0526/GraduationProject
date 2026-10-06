"""独立副本从相同输入运行；原封存、旧评价与失败输出均保留。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
worker=(here/'612-稳定原生四类输入阶段耗时隔离诊断.py').read_text('utf8')
worker=worker.replace("if profile:env['GEO_NATIVE_STAGE_TIMING']='1'","if profile:env.pop('GEO_NATIVE_STAGE_TIMING',None)")
worker=worker.replace('stage_profile_01','keep_skip_comparison_01').replace('01-稳定原生四类输入阶段诊断实际记录','01-免重复判定四类实际比较记录')
worker=worker.replace('首次四类输入实际分阶段诊断','首次免重复判定四类实际开发比较').replace('仅诊断，不新增参数、几何放宽或正式性能结论；同方法正式副本单次参照','免重复判定开发副本三次测量；旧封存同输入一次参照，不作为完整分布或独立评价')
(here/'627-免重复判定四类同输入实际比较.py').write_text(worker,'utf8')
controller=(here/'613-稳定原生四类输入阶段诊断上传取回.py').read_text('utf8')
for old,new in [('20261007_31','20261007_32'),('612-稳定原生四类输入阶段耗时隔离诊断','627-免重复判定四类同输入实际比较'),('614-稳定原生四类输入阶段诊断实际取回记录','629-免重复判定四类实际取回记录'),('615-稳定原生四类输入阶段诊断控制台日志','630-免重复判定四类实际比较日志'),('616-稳定原生四类输入阶段诊断完整归档','631-免重复判定四类实际比较完整归档'),('stage_profile_01','keep_skip_comparison_01'),('01-稳定原生四类输入阶段诊断实际记录','01-免重复判定四类实际比较记录')]:
    controller=controller.replace(old,new)
controller=controller.replace("record.update(worker_status=worker['status'],actual_calls=len(worker['rows']))","record.update(status='completed_actual_comparison_retrieved',worker_status=worker['status'],actual_calls=len(worker['rows']))")
(here/'628-免重复判定四类比较上传取回.py').write_text(controller,'utf8')
manifest=json.loads((here/'597-保留好区顶点原生CT十六刀冻结清单.json').read_text('utf8'))
manifest.update(生成时间=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),修改时间及修改内容='首次绑定免重复判定版本完整CT16输入',
    candidate_build_sha256=sha(here/'625-已保留接缝顶点免重复判定原生构建记录.json'),candidate_manifest_sha256=sha(here/'620-已保留接缝顶点免重复判定源码清单.json'))
(here/'632-免重复判定完整CT十六刀输入清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
(here/'633-免重复判定完整CT十六刀反馈.py').write_text((here/'598-保留好区顶点原生CT十六刀反馈.py').read_text('utf8'),'utf8')
controller=(here/'599-保留好区顶点原生CT十六刀上传取回.py').read_text('utf8')
for old,new in [('20261007_30','20261007_32'),('597-保留好区顶点原生CT十六刀冻结清单','632-免重复判定完整CT十六刀输入清单'),('598-保留好区顶点原生CT十六刀反馈','633-免重复判定完整CT十六刀反馈'),('600-保留好区顶点原生CT十六刀实际取回记录','635-免重复判定完整CT十六刀实际取回记录'),('601-保留好区顶点原生CT十六刀实际控制台日志','636-免重复判定完整CT十六刀实际控制台日志'),('602-保留好区顶点原生CT十六刀完整归档','637-免重复判定完整CT十六刀完整归档')]:
    controller=controller.replace(old,new)
(here/'634-免重复判定完整CT十六刀上传取回.py').write_text(controller,'utf8')
print('prepared_twenty_same_input_calls_and_sixteen_feedback_events')
