"""三源三轮全部方法保存复审，并为新候选重算原外部面与固定点契约。"""
from pathlib import Path
import sys
import recheck_ordered_features
from recheck_ordered_pairs import build_pair_recheck
from preserved_controller_source import replace_once


def build_active_pair_recheck(source):
    source=build_pair_recheck(source)
    marker='                accepted=bool(valid and topology'
    inserted='''                if method=='boolean':
                    bits=json.loads(labels_path.read_text(encoding='utf-8'))['operand_bits']
                    active,fixed=make_masks(source,bits,None,'boolean',2,allow_shared=True)
                    external=fixed_surface_contract(source,mesh,active,fixed)
                    saved=row['original_activity_external_face_contract']
                    contract=contract and external['passed'] and external=={key:saved[key] for key in external} and saved['rings']==2
                    item['original_activity_external_face_contract']=external
'''
    return replace_once(source,marker,inserted+marker)


if __name__=='__main__':
    output=Path(sys.argv[sys.argv.index('--output')+1])
    source=build_active_pair_recheck(Path(recheck_ordered_features.__file__).read_text(encoding='utf-8'))
    path=output/'recheck_active_pair_snapshot.py';path.write_text(source,encoding='utf-8')
    exec(compile(source,str(path),'exec'),dict(__name__='__main__',__file__=str(path)))
