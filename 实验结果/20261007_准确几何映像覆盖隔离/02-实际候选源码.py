"""抵消必要修复产生的严格反向面；顶点坐标不动，最终嵌入由调用方精确认证。"""
from time import perf_counter
from fractions import Fraction
import numpy as np


def cancel_opposed_index_faces(vertices,faces,bits):
    start=perf_counter()
    _,groups,counts=np.unique(np.sort(faces,axis=1),axis=0,return_inverse=True,return_counts=True)
    # 反向关系按同一组顶点编号及排列奇偶严格判断，不按近似平面或小面积删除面。
    inversions=(faces[:,0]>faces[:,1]).astype(np.int8)+(faces[:,0]>faces[:,2]).astype(np.int8)+(faces[:,1]>faces[:,2]).astype(np.int8)
    live=np.ones(len(faces),dtype=bool);pairs=[]
    for group in np.flatnonzero(counts==2):
        ids=np.flatnonzero(groups==group)
        if inversions[ids[0]]%2!=inversions[ids[1]]%2:
            live[ids]=False;pairs.append(ids.tolist())
    new_faces,new_bits=faces[live],bits[live]
    return vertices,new_faces,new_bits,dict(removed_opposed_face_pairs=pairs,removed_faces=int((~live).sum()),
        vertices_bitwise_unchanged=True,decision='只抵消同顶点编号的唯一反向面组；不保证删除面所在点集距离为零',
        total_elapsed_ms=(perf_counter()-start)*1000)


def repair_short_edge_clusters(vertices,faces,bits,parent_vertices,tolerance_mm=1e-10,prune_uncovered=False,geometric_coverage=False):
    """提出整体极短边替换；调用方必须认证后才提交，函数不宣称候选已合法。"""
    start=perf_counter();v=np.asarray(vertices);f=np.asarray(faces);labels=np.asarray(bits)
    edges=np.unique(np.sort(np.vstack((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]])),axis=1),axis=0)
    short=edges[np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1)<=tolerance_mm]
    roots={int(i):int(i) for i in np.unique(short)}
    def root(i):
        while roots[i]!=i:roots[i]=roots[roots[i]];i=roots[i]
        return i
    for a,b in short:
        a,b=root(int(a)),root(int(b))
        if a!=b:roots[b]=a
    groups={}
    for i in roots:groups.setdefault(root(i),[]).append(i)
    mapping=np.arange(len(v));operations=[];rejections=[]
    parent=np.asarray(parent_vertices);bound_squared=Fraction.from_float(tolerance_mm)**2
    for group in groups.values():
        anchors=[i for i in group if np.any(np.all(parent==v[i],axis=1))]
        if anchors and any(not np.array_equal(v[i],v[anchors[0]]) for i in anchors):
            rejections.append(dict(vertices=group,reason='成组包含坐标不同的父锚点'));continue
        keep=min(anchors or group);squares=[]
        for i in group:
            squares.append(sum((Fraction.from_float(float(v[i,k]))-Fraction.from_float(float(v[keep,k])))**2 for k in range(3)))
        if max(squares)>bound_squared:
            rejections.append(dict(vertices=group,reason='传递分组超出原准确位移界'));continue
        mapping[group]=keep
        operations.append(dict(vertices=group,keep=keep,parent_anchors=anchors,
            maximum_distance_squared_numerator=str(max(squares).numerator),maximum_distance_squared_denominator=str(max(squares).denominator)))
    rational_points={}
    def image_inside_triangle(points,triangle):
        # 准确共面和三个有向半平面判定；全部像点落在同一闭三角形内即可覆盖其凸包。
        def point(i):
            if i not in rational_points:rational_points[i]=tuple(Fraction.from_float(float(x)) for x in v[i])
            return rational_points[i]
        a,b,c=map(point,map(int,triangle));u=[b[k]-a[k] for k in range(3)];w=[c[k]-a[k] for k in range(3)]
        normal=[u[(k+1)%3]*w[(k+2)%3]-u[(k+2)%3]*w[(k+1)%3] for k in range(3)]
        axis=max(range(3),key=lambda k:abs(normal[k]))
        if not normal[axis]:return False
        x,y=(axis+1)%3,(axis+2)%3
        orient=lambda p,q,r:(q[x]-p[x])*(r[y]-p[y])-(q[y]-p[y])*(r[x]-p[x])
        side=orient(a,b,c)
        for i in points:
            p=point(i)
            if sum(normal[k]*(p[k]-a[k]) for k in range(3))!=0:return False
            if any(orient(p0,p1,p)*side<0 for p0,p1 in [(a,b),(b,c),(c,a)]):return False
        return True
    while True:
        proposed=mapping[f];live=np.all(np.diff(np.sort(proposed,axis=1),axis=1)!=0,axis=1)
        surviving=proposed[live];surviving_bits=labels[live];coverage=[];uncovered=[]
        # 被压缩成点或线的面必须由同标签保留面覆盖；失败分组可撤销，但覆盖前提不放宽。
        for index in np.flatnonzero(~live):
            tri=proposed[index];eligible=surviving[surviving_bits==labels[index]]
            points=sorted(set(map(int,tri)));segments=sorted({tuple(sorted((int(tri[k]),int(tri[(k+1)%3])))) for k in range(3) if tri[k]!=tri[(k+1)%3]})
            covered=all(np.any(eligible==i) for i in points) and all(np.any(np.any(eligible==a,axis=1)&np.any(eligible==b,axis=1)) for a,b in segments)
            geometric_face=None
            if not covered and geometric_coverage:
                # 原编号覆盖不足时只允许准确几何覆盖；包围盒仅筛选，不作为覆盖证明。
                ids=np.flatnonzero(live)[surviving_bits==labels[index]];triangles=v[eligible]
                lower,upper=v[points].min(axis=0),v[points].max(axis=0)
                candidates=np.flatnonzero(np.all(triangles.min(axis=1)<=lower,axis=1)&np.all(triangles.max(axis=1)>=upper,axis=1))
                for candidate in candidates:
                    if image_inside_triangle(points,eligible[candidate]):
                        geometric_face=int(ids[candidate]);covered=True;break
            if not covered:
                if not prune_uncovered:
                    return v,f,labels,dict(candidate=False,reason='成组退化映像缺少同标签覆盖',operations=operations,
                        rejections=rejections,total_elapsed_ms=(perf_counter()-start)*1000)
                uncovered.append(int(index))
            else:
                entry=dict(original_face=int(index),source_bit=int(labels[index]),image_points=points,image_edges=segments)
                if geometric_face is not None:entry['exact_geometric_cover_original_face']=geometric_face
                coverage.append(entry)
        if not uncovered:break
        affected=set(map(int,f[uncovered].ravel()));retained=[]
        for operation in operations:
            if affected.intersection(operation['vertices']):
                rejections.append(dict(vertices=operation['vertices'],reason='同标签覆盖失败的关联成组撤销',uncovered_original_faces=uncovered))
            else:retained.append(operation)
        if len(retained)==len(operations):raise ValueError('覆盖失败却没有可撤销分组')
        # 每轮至少撤销一组，有限结束；重新检查所有剩余压缩面，不能沿用旧覆盖记录。
        operations=retained;mapping=np.arange(len(v))
        for operation in operations:mapping[operation['vertices']]=operation['keep']
    # 按实际活跃边求连通分量及各分量欧拉特征；完整闭合嵌入仍须调用方认证。
    def signature(triangles):
        unique_edges=np.unique(np.sort(np.vstack((triangles[:,[0,1]],triangles[:,[1,2]],triangles[:,[2,0]])),axis=1),axis=0)
        parents=np.arange(len(v))
        def find(i):
            while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
            return i
        for a,b in unique_edges:
            a,b=find(a),find(b)
            if a!=b:parents[b]=a
        counts={}
        for i in np.unique(triangles):counts.setdefault(find(i),[0,0,0])[0]+=1
        for edge in unique_edges:counts[find(edge[0])][1]+=1
        for tri in triangles:counts[find(tri[0])][2]+=1
        return sorted(int(a-b+c) for a,b,c in counts.values())
    before,after=signature(f),signature(surviving)
    accepted=before==after and bool(operations)
    result=dict(candidate=accepted,reason='等待原精确闭合嵌入与连通分量认证' if accepted else '欧拉特征变化或没有可用分组',
        operations=operations,rejections=rejections,removed_faces=int((~live).sum()),coverage=coverage,
        component_euler_before=before,component_euler_after=after,vertices_bitwise_unchanged=True,
        original_tolerance_mm=tolerance_mm,total_elapsed_ms=(perf_counter()-start)*1000)
    return (v,surviving,surviving_bits,result) if accepted else (v,f,labels,result)
