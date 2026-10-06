"""仅整理交接输入；C/D原始资产只读，109份冻结输入逐字节归档，不执行算法。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import zipfile

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日 %H:%M:%S')
record={'生成时间':now+'（北京时间）','修改时间及修改内容':now+'（北京时间），首次交接输入原字节归档',
    '文档概述':'旧30输入、第二批16输入和CT16初态工具的109份引用全部迁移；仅保留原数据及历史路径映射，不执行算法、不冒充未见输入',
    '索引目录':['groups','objects'],'status':'preparing','groups':{},'objects':[]}
for pattern,group in [('526-*.json','已见三十输入'),('574-*.json','第二批十六输入')]:
    manifest=next(here.glob(pattern));data=json.loads(manifest.read_text('utf8'))
    record['groups'][group]={'historical_manifest':manifest.name,'historical_manifest_sha256':sha(manifest),'cases':len(data['cases'])}
    for i,case in enumerate(data['cases']):
        for role in ['parent','tool']:
            source=Path(case[role]);assert sha(source)==case[role+'_sha256']
            record['objects'].append({'group':group,'index':i,'role':role,'id':case['id'],'historical_source_path':str(source),
                'sha256':case[role+'_sha256'],'portable_file':f'{group}/{i:02d}_{role}.obj','bytes':source.stat().st_size})
manifest=next(here.glob('632-*.json'));data=json.loads(manifest.read_text('utf8'));group='原生CT十六刀'
record['groups'][group]={'historical_manifest':manifest.name,'historical_manifest_sha256':sha(manifest),'tools':len(data['tools'])}
for role,i,item in [('initial',-1,data['initial'])]+[('tool',i,item) for i,item in enumerate(data['tools'])]:
    source=here/'原生CT十六刀开发冻结输入'/item['file'];assert sha(source)==item['sha256']
    record['objects'].append({'group':group,'index':i,'role':role,'historical_source_path':str(source),'sha256':item['sha256'],
        'portable_file':group+'/'+item['file'],'bytes':source.stat().st_size})
assert len(record['objects'])==109
archive=here/'674-Geogram换机继续全部109输入原字节归档.zip';assert not archive.exists()
record.update(status='frozen_all_109_portable_input_references',objects_count=109)
mapping=here/'673-Geogram换机109输入路径与摘要映射.json';assert not mapping.exists()
mapping.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
    z.write(mapping,mapping.name)
    for item in record['objects']:z.write(item['historical_source_path'],item['portable_file'])
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and len(z.namelist())==110
    assert all(hashlib.sha256(z.read(item['portable_file'])).hexdigest()==item['sha256'] for item in record['objects'])
report=next(here.parent.parent.glob('220-*.md'));text=report.read_text('utf8')
anchor='不要在公开文档、普通ZIP、仓库提交或日志里携带SSH密码。'
assert text.count(anchor)==1
paragraph='旧30输入中有D盘引用，直接只复制C盘项目会漏掉这些输入。已新增[674号全部109输入归档](实验结果/20261006_Geogram内核质量生成/'+archive.name+')和[673号历史路径与摘要映射](实验结果/20261006_Geogram内核质量生成/'+mapping.name+')：30×2+16×2+CT初态及16工具共109引用，归档CRC及每份SHA全部核对。原始C/D文件和旧清单未改；109不代表109个独立案例。换机解压后按portable_file定位，建立新的运行路径映射即可摆脱旧D盘绝对路径。旧输入均已见，不因迁移而恢复未见身份。\n\n'
text=text.replace(anchor,paragraph+anchor)
text=re.sub(r'\*\*修改时间及修改内容\*\*：[^\n]+',f'**修改时间及修改内容**：{now}（北京时间），首次交接后补充109份跨盘输入原字节归档与迁移映射；用户要求的暂停保持。',text,count=1)
report.write_text(text,'utf8')
print('handoff_portable_inputs_verified',len(record['objects']),archive.stat().st_size,sha(archive),flush=True)
