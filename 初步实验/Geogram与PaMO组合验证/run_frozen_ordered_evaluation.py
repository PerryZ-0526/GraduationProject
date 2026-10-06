"""只从冻结入口及依赖执行完整保留评价，投影前核对实际生成源码版本。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from audit_followup_candidate import sha256
from preserved_controller_source import replace_once


def verify_freeze(folder, prepared):
    record=json.loads((folder/'01-方法与保留评价完整冻结.json').read_text(encoding='utf-8'))
    if sha256(prepared/'01-完整范围冻结清单.json')!=record['manifest_sha256']:
        raise ValueError('评价清单与冻结不一致')
    for row in record['method_files']+record['runtime_files']:
        path=(folder/row['file']).resolve()
        if not path.is_relative_to(folder.resolve()) or sha256(path)!=row['sha256']:
            raise ValueError('冻结方法或运行依赖变化')
    for row in record['inputs']:
        path=(prepared/'inputs'/row['file']).resolve()
        if not path.is_relative_to((prepared/'inputs').resolve()) or sha256(path)!=row['sha256']:
            raise ValueError('冻结评价输入变化')
    return record


def expected_generated_sources(record):
    names={'initial_encoding_worker.py','planar_patch.py','preserved_reference.py','preserved_controller.py',
        'ordered_physical_cleanup.py','ordered_physical_cleanup_snapshot.py','physical_feedback_entry.py'}

    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key.endswith(('.py','.cpp')) and isinstance(item,str) and len(item)==64:
                    names.add(key)
                visit(item)
        elif isinstance(value,list):
            for item in value:
                visit(item)
    visit(record['actual_environment'])
    # 只比较开发实际生成目录的对象，原基础源码另由运行依赖冻结绑定。
    expected={Path(r['file']).name:r['sha256'] for r in record['method_files'] if Path(r['file']).name in names}
    if not {'initial_encoding_worker.py','planar_patch.py','preserved_reference.py'}.issubset(expected):
        raise ValueError('实际工作器版本冻结缺失')
    return expected


def build_bound_entry(source, expected):
    inserted='''        # 候选结果打开前核对实际生成的投影、参照和清理副本。
        expected_generated_sources = EXPECTED_GENERATED_SOURCES
        for name, digest in expected_generated_sources.items():
            if sha256(self.output/name) != digest:
                raise ValueError("评价实际生成源码与开发冻结不一致："+name)
        info['evaluation_generated_sources_verified'] = expected_generated_sources
'''.replace('EXPECTED_GENERATED_SOURCES',repr(expected))
    return replace_once(source,'        info=super().setup()\n','        info=super().setup()\n'+inserted)


def release_or_verify_entry(path, source):
    """复跑只复用完全一致的生成入口，不覆盖已有源码。"""
    data=source.replace('\n',os.linesep).encode('utf-8')
    if path.exists():
        if path.read_bytes()!=data:
            raise ValueError('已有封存执行入口与当前冻结版本不符')
        return
    # 与原文本写入保持相同字节格式，新的输出批次仍由控制器禁止覆盖。
    with path.open('xb') as stream:
        stream.write(data)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('freeze','prepared','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args()
    record=verify_freeze(args.freeze,args.prepared)
    runtime=args.freeze/'运行入口与依赖'
    source=(runtime/record['execution_entry']).read_text(encoding='utf-8')
    entry=runtime/'released_evaluation_entry.py'
    release_or_verify_entry(entry,build_bound_entry(source,expected_generated_sources(record)))
    # 独立进程从冻结目录导入，避免主仓后续改动被评价期间动态读取。
    result=subprocess.run([sys.executable,str(entry.resolve()),'--prepared',str(args.prepared.resolve()),
        '--output',str(args.output.resolve()),'--port',str(args.port),'--split','evaluation'])
    raise SystemExit(result.returncode)
