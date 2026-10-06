"""仅在原活动面内生成共面三角形，保留原活动域外的有向面集合。"""
from pathlib import Path
from preserved_controller_source import replace_once


def build_active_source(source):
    source=replace_once(source,'if seed in visited or mesh.area_faces[seed] <= 1e-12:',
        'if seed in visited or not active[seed] or mesh.area_faces[seed] <= 1e-12:')
    # 共面邻接搜索也受原活动面约束，不仅限制种子点。
    return replace_once(source,'            if face in visited:\n',
        '            if face in visited or not active[face]:\n')


SOURCE=build_active_source((Path(__file__).resolve().parent/'planar_patch.py').read_text(encoding='utf-8'))
NAMESPACE=dict(__name__='active_planar_regions')
exec(compile(SOURCE,'active_planar_regions','exec'),NAMESPACE)
rebuild_planar_regions=NAMESPACE['rebuild_planar_regions']
