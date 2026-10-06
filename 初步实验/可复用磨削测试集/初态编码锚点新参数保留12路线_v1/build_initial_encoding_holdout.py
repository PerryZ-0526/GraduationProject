"""生成新参数骨样体及有效表面接触路线，不筛选维护结果。"""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import numpy as np
from build_cases import make_body, digest
from prepare_feedback import make_route, save_obj_fp64

FAMILIES=('板体','板体','球体','球体','椭球','椭球','弯曲骨样体','弯曲骨样体','贯通孔','薄壁','薄壁','窄缝')


def contact_motion(mesh, angle):
    # 刀位只由原表面最大三角面确定，不读取质量维护或接受结果。
    face=int(np.argmax(mesh.area_faces))
    normal=mesh.face_normals[face]
    tangent=mesh.triangles[face,1]-mesh.triangles[face,0]
    tangent=tangent/np.linalg.norm(tangent)
    bitangent=np.cross(normal,tangent)
    u=np.cos(angle)*tangent+np.sin(angle)*bitangent
    v=-np.sin(angle)*tangent+np.cos(angle)*bitangent
    radius=min(.55,float(mesh.extents.min())*.25)
    anchor=mesh.triangles_center[face]
    center=anchor+normal*radius*.35
    offsets=np.array([[-.6,-.4],[.6,.4],[-.6,.4],[.6,-.4],[-.6,-.4]])
    points=center+radius*(offsets[:,0,None]*u+offsets[:,1,None]*v)
    return dict(tool_radius_mm=radius,events=[dict(position_mm=p.tolist()) for p in points]), dict(
        source_face_index=face, surface_anchor_mm=anchor.tolist(), normal=normal.tolist(),
        tangent_u=u.tolist(),tangent_v=v.tolist(),normal_offset_radius_fraction=.35)


def build(output):
    output.mkdir(parents=True,exist_ok=False)
    inputs=output/'inputs';inputs.mkdir()
    rng=np.random.default_rng(2026100501)
    old=Path(__file__).resolve().parent/'合成输入_v1/01-测试集清单.json'
    old_manifest=json.loads(old.read_text(encoding='utf-8'))
    old_hashes={body['sha256'] for body in old_manifest['bodies']}
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        generator_sha256=digest(Path(__file__)),seed=2026100501,routes=[],negative_inputs=[],
        units=dict(length='mm',time='ms'),replay_policy=dict(late_event='reject',max_link_gap_ms=200),
        scope='12个新连续参数合成体、各4段表面接触；同既有形状家族，非新患者或新形状家族；维护输出尚未打开',
        selection_policy='预定家族顺序与随机种子，不根据布尔、投影或验收输出筛选',
        prior_body_manifest_sha256=digest(old),algorithm_results_opened=False)
    for index,family in enumerate(FAMILIES):
        variant=float(rng.uniform(.15,4.85));angle=float(rng.uniform(-np.pi,np.pi))
        mesh=make_body(family,variant)
        body_id='保留参数_'+str(index+1).zfill(2)+'_'+family
        path=inputs/(body_id+'.obj');save_obj_fp64(mesh,path)
        if digest(path) in old_hashes:
            raise ValueError('新体与旧35体摘要重复，禁止重新标记独立输入')
        motion,anchor=contact_motion(mesh,angle)
        route=make_route(dict(id=body_id),'表面交叉',motion,path,inputs,'evaluation','synthetic_new_parameters')
        route.update(family=family,variant_parameter=variant,angle_radians=angle,cut_anchor=anchor,
            intended_contact=True,simulation=True)
        report['routes'].append(route)
    (output/'build_initial_encoding_holdout.py').write_bytes(Path(__file__).read_bytes())
    (output/'build_cases.py').write_bytes(Path(__file__).with_name('build_cases.py').read_bytes())
    (output/'01-完整范围冻结清单.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    report=build(parser.parse_args().output)
    print('new bodies',len(report['routes']),'events',sum(len(r['cutting_prefix_ids']) for r in report['routes']))
