"""复用小特征逐对象复审，核对三源三轮四方法完整分母及同次上传摘要。"""
from pathlib import Path
import sys
import recheck_ordered_features
from preserved_controller_source import replace_once


def build_pair_recheck(source):
    source = replace_once(source, "manifest_path = args.prepared/'01-完整范围冻结清单.json'", "manifest_path = args.prepared/'01-冻结清单.json'")
    source = replace_once(source, "record_path = args.output/'02-浅磨特征保持审计.json'", "record_path = args.output/'01-三源三轮四方法同输入比较.json'")
    source = replace_once(source, "'completed_with_recorded_failures'", "'completed_with_recorded_outcomes'")
    start = source.index('    expected = ')
    end = source.index('    certificates = ', start)
    # 三轮和四方法逐项覆盖；真实输入前提失败不能伪造工作器返回证据。
    source = source[:start]+'''    expected = {(item['id'],round_id,method) for item in manifest['cases'] for round_id in range(3) for method in ('full','global','spatial','boolean')}
    actual = [(r['case'],r['round'],r['declared_method']) for r in report['rows']]
    if len(actual)!=len(expected) or set(actual)!=expected:
        raise ValueError('三源三轮四方法完整分母缺失或重复')
    if any('execution' not in row for row in report['rows']):
        raise ValueError('本复审要求实际执行证据；输入前提拒绝需单独负例审计')
'''+source[end:]
    source = replace_once(source, "tool_path = args.output/tools[case]['tool']", "tool_path = source_path.with_name('tool.obj')")
    source = replace_once(source, "if inputs != row.get('inputs_sha256') or sha256(tool_path) != tools[case]['sha256']:", "if inputs != row.get('inputs_sha256') or inputs != row['same_input_sha256']:")
    source = replace_once(source, "folder = args.output/(case+'_'+method)", "folder = args.output/(case+'_r'+str(row['round'])+'_'+method)\n            if str(folder.resolve()) != row['artifact_directory']:\n                raise ValueError('返回对象目录与执行记录不一致')")
    source = replace_once(source, "item = dict(case=case,method=method,", "item = dict(case=case,round=row['round'],method=method,")
    source = replace_once(source, ",\n                    geometry_to_feature_width_ratio=geometry['probe_max_mm']/row['feature_width_mm']", "")
    source = replace_once(source, "03-小特征完整分母与保存对象复审.json", "02-三源三轮完整分母与保存对象复审.json")
    source = replace_once(source, "完整36条分母、同次上传输入、实际返回网格与拒绝证据重审；不证明连续误差或孔径数值界", "三源三轮四方法36条分母、同次上传输入、实际返回网格和失败证据；非独立新输入或连续距离证书")
    return source


if __name__=='__main__':
    output = Path(sys.argv[sys.argv.index('--output')+1])
    source = build_pair_recheck(Path(recheck_ordered_features.__file__).read_text(encoding='utf-8'))
    snapshot = output/'recheck_ordered_pairs_snapshot.py'
    snapshot.write_text(source,encoding='utf-8')
    exec(compile(source,str(snapshot),'exec'),dict(__name__='__main__',__file__=str(snapshot)))
