"""重加载活动面限定六次GPU投影，核对实际输入、锚点及原外部面契约。"""
from pathlib import Path
import sys
import recheck_ordered_features
from preserved_controller_source import replace_once


def build_recheck(source):
    start=source.index('    manifest_path = ')
    end=source.index('    certificates = ',start)
    source=source[:start]+'''    previous_path=args.prepared/'01-三源三轮四方法同输入比较.json'
    previous=json.loads(previous_path.read_text(encoding='utf-8'))
    record_path=args.output/'01-活动面限制三源完整GPU投影.json'
    report=json.loads(record_path.read_text(encoding='utf-8'))
    if report['status']!='completed_with_recorded_outcomes' or sha256(previous_path)!=report['previous_record_sha256']:
        raise ValueError('新投影终态或前次实际输入记录不符')
    cases=[r for r in previous['rows'] if r['declared_method']=='boolean' and r['round']==0]
    expected={(r['case'],method) for r in cases for method in ('boolean','expanded')}
    actual=[(r['case'],r['region']) for r in report['rows']]
    if len(cases)!=3 or len(actual)!=6 or set(actual)!=expected:
        raise ValueError('三源两区域完整分母缺失或重复')
    tools={r['case']:r['same_input_sha256'] for r in cases}
'''+source[end:]
    source=replace_once(source,"case,method = row['case'],row.get('feature_method',row.get('method'))","case,method = row['case'],row['region']")
    source=replace_once(source,"source_path = args.output/(case+'_input')/'clean_source.obj'","source_path = args.prepared/(case+'_input')/'clean_source.obj'")
    source=replace_once(source,"tool_path = args.output/tools[case]['tool']","tool_path = source_path.with_name('tool.obj')")
    source=replace_once(source,"if inputs != row.get('inputs_sha256') or sha256(tool_path) != tools[case]['sha256']:","if inputs != row.get('inputs_sha256') or inputs != tools[case]:")
    source=replace_once(source,"if method=='boolean':","if method in ('boolean','expanded'):")
    source=replace_once(source,"(method=='boolean' or metrics['fp32_zero_area_faces']==0)","(method in ('boolean','expanded') or metrics['fp32_zero_area_faces']==0)")
    marker='                accepted=bool(valid and topology'
    inserted='''                # 原活动域由同次标签确定，不以输出删除的点重定义外部。
                bits=json.loads(labels_path.read_text(encoding='utf-8'))['operand_bits']
                active,fixed=make_masks(source,bits,trimesh.load(tool_path,process=False),'boolean',4 if method=='expanded' else 2,allow_shared=True)
                external=fixed_surface_contract(source,mesh,active,fixed)
                contract=contract and external['passed'] and external==row['original_activity_external_face_contract']
                item['original_activity_external_face_contract']=external
'''
    source=replace_once(source,marker,inserted+marker)
    source=replace_once(source,",\n                    geometry_to_feature_width_ratio=geometry['probe_max_mm']/row['feature_width_mm']",'')
    source=replace_once(source,'03-小特征完整分母与保存对象复审.json','02-活动面限制保存对象及外部契约复审.json')
    source=replace_once(source,'完整36条分母、同次上传输入、实际返回网格与拒绝证据重审；不证明连续误差或孔径数值界',
        '三源两区域六次实际保存投影、原外部面与点、初态及新增锚点、精确嵌入和几何；非连续或新输入证明')
    return source


if __name__=='__main__':
    output=Path(sys.argv[sys.argv.index('--output')+1])
    source=build_recheck(Path(recheck_ordered_features.__file__).read_text(encoding='utf-8'))
    path=output/'recheck_active_patch_snapshot.py';path.write_text(source,encoding='utf-8')
    exec(compile(source,str(path),'exec'),dict(__name__='__main__',__file__=str(path)))
