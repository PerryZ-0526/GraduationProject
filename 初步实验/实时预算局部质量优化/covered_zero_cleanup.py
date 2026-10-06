"""复用质量线路的精确零面覆盖规则，用向量查询避免构建全量Python边字典。"""
from time import perf_counter
import numpy as np


def clean_arrays(vertices,faces,bits):
    start=perf_counter();labels=np.asarray(bits)
    if len(labels)!=len(faces) or np.any(~np.isin(labels,[1,2,3])):raise ValueError('来源位不合法')
    v,inverse=np.unique(vertices,axis=0,return_inverse=True);mapped=inverse[faces]
    keep=(mapped[:,0]!=mapped[:,1])&(mapped[:,1]!=mapped[:,2])&(mapped[:,2]!=mapped[:,0])
    certificates=[]
    def contains(point):
        # 逐列布尔查询与三轴归约相同，只查几条零面映像所需的点和边。
        return (mapped[:,0]==point)|(mapped[:,1]==point)|(mapped[:,2]==point)
    for index in np.flatnonzero(~keep):
        tri=mapped[index];label=labels[index];allowed=keep&(labels==label)
        points=sorted(set(map(int,tri)));hits={p:contains(p) for p in points}
        edges=sorted({tuple(sorted((int(tri[k]),int(tri[(k+1)%3])))) for k in range(3) if tri[k]!=tri[(k+1)%3]})
        point_support=[];edge_support=[]
        for p in points:
            ids=np.flatnonzero(allowed&hits[p])
            if not len(ids):raise ValueError('零面点映像缺少同标签覆盖')
            point_support.append(int(ids[0]))
        for a,b in edges:
            ids=np.flatnonzero(allowed&hits[a]&hits[b])
            if not len(ids):raise ValueError('零面线段映像缺少同标签覆盖')
            edge_support.append(int(ids[0]))
        certificates.append(dict(original_face_id=int(index),source_label=int(label),exact_vertex_ids=tri.tolist(),
            image_edges=[list(e) for e in edges],edge_support_face_ids=edge_support,point_support_face_ids=point_support,
            point_ids=points,set_distance_upper_bound_mm=0.0))
    f=mapped[keep];new_bits=labels[keep].copy()
    # 全部保留面的三维坐标逐项不变；不删除三不同点共线面，也不合并近邻坐标。
    if not np.array_equal(v[f],vertices[faces[keep]]):raise AssertionError('规范化改变保留面坐标')
    result=dict(method='exact_weld_same_label_covered_zero',
        original_vertices=len(vertices),output_vertices=len(v),removed_faces=int((~keep).sum()),
        surviving_original_face_ids=np.flatnonzero(keep).tolist(),zero_face_deletions=certificates,
        geometric_image_change_mm=0.0,topology_and_embedding_require_audit=True)
    # 证书和存活面编号的组织也计入源规范化时间。
    result['elapsed_ms']=(perf_counter()-start)*1000
    return v,f,new_bits,result
