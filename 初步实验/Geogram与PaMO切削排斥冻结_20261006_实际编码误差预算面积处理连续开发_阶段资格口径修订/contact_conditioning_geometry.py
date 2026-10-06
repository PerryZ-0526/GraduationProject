"""以真实接触短边生成端点折叠，保留原邻面平面、方向和面积预算。"""
import numpy as np

def endpoint_collapse(vertices, faces, edge, encoded_vertices, scale):
    vertices=np.asarray(vertices);faces=np.asarray(faces);q=np.asarray(encoded_vertices,dtype=np.float64)
    a,b=sorted(map(int,edge));physical=q/scale
    shared=np.sum(np.isin(faces,[a,b]),axis=1)==2
    if shared.sum()!=2:return None,{'reason':'two_shared_faces'}
    na=set(faces[np.any(faces==a,axis=1)].ravel())-{a}
    nb=set(faces[np.any(faces==b,axis=1)].ravel())-{b}
    if na&nb!=set(faces[shared].ravel())-{a,b}:return None,{'reason':'link_condition'}
    changed=np.any(np.isin(faces,[a,b]),axis=1)&~shared
    old=physical[faces[changed]];normal=np.cross(old[:,1]-old[:,0],old[:,2]-old[:,0]);length=np.linalg.norm(normal,axis=1)
    if not len(length) or np.any(length<=2e-12):return None,{'reason':'small_original_incident_face'}
    normal/=length[:,None];rejections=[]
    # 优先保留编号较小的原端点，失败才尝试另一个端点；不创建移动点或扩展预算。
    for keep,drop in [(a,b),(b,a)]:
        plane=np.abs(np.sum((physical[keep]-old[:,0])*normal,axis=1))
        if np.any(plane>1e-8):rejections.append('original_plane_budget');continue
        replacement=faces.copy();replacement[replacement==drop]=keep;new_faces=replacement[~shared]
        if len(np.unique(np.sort(new_faces,axis=1),axis=0))!=len(new_faces):rejections.append('duplicate_face');continue
        new=physical[replacement[changed]];nn=np.cross(new[:,1]-new[:,0],new[:,2]-new[:,0])
        if np.any(np.sum(nn*normal,axis=1)<=2e-12):rejections.append('orientation_or_projected_area');continue
        triangles=physical[new_faces];area=.5*np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)
        if np.any(area<=1e-12) or not np.isfinite(area).all():rejections.append('final_physical_area');continue
        ids=np.unique(new_faces);mapping=np.full(len(vertices),-1,dtype=int);mapping[ids]=np.arange(len(ids))
        result=(vertices[ids].copy(),mapping[new_faces],q[ids].astype(np.float32))
        record={'edge':[a,b],'kept_original_vertex':keep,'deleted_original_vertex':drop,'remaining_original_vertex_ids':ids.tolist(),'max_original_incident_plane_deviation_mm':float(plane.max()),'plane_budget_mm':1e-8,'minimum_area_mm2':float(area.min()),'changed_faces':int(changed.sum()),'deleted_faces':int(shared.sum()),'rejections':rejections}
        return result,record
    return None,{'reason':'no_legal_endpoint','rejections':rejections}

def bad_contact_edges(contact_indices, contact_types, q):
    # 当前机制仅覆盖已经证明的内部边边接触；其他失稳保持拒绝，不任意改分类。
    edges=set()
    for ids,kind in zip(contact_indices,contact_types):
        if tuple(kind)!=(4,8):continue
        pair=[tuple(sorted(map(int,ids[:2]))),tuple(sorted(map(int,ids[2:])))]
        edges.add(min(pair,key=lambda edge:(float(np.linalg.norm(q[edge[0]]-q[edge[1]])),edge)))
    return sorted(edges,key=lambda edge:(float(np.linalg.norm(q[edge[0]]-q[edge[1]])),edge))
