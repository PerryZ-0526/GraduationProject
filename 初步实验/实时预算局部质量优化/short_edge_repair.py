"""在预算内收缩CSG新增极短边，保留父帧锚点及逐标签退化映像覆盖证书。"""
from fractions import Fraction
from math import sqrt,nextafter,inf
from time import perf_counter
import numpy as np
from local_guard import separated_except_shared


def repair_short_edges(vertices,faces,bits,parent_vertices,budget_ms,tolerance_mm=1e-10,max_collapses=16,separation_check=separated_except_shared):
    start=perf_counter();deadline=start+max(0,budget_ms-2)/1000
    v=np.asarray(vertices);f=np.asarray(faces).copy();labels=np.asarray(bits).copy();operations=[];rejections=[]
    if len(labels)!=len(f) or np.any(~np.isin(labels,[1,2,3])):raise ValueError('来源位长度或编码不合法')
    a,b,c=(v[f[:,k]] for k in range(3));low=np.minimum(np.minimum(a,b),c);high=np.maximum(np.maximum(a,b),c)
    edges=np.concatenate((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]));edges.sort(axis=1)
    distance=np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1)
    candidates=np.unique(edges[distance<=tolerance_mm],axis=0)
    # 只查询候选端点是否为父锚点；未完成查询的端点保守地视为不可移动。
    anchored=np.ones(len(v),dtype=bool)
    parent=np.asarray(parent_vertices)
    for point_id in np.unique(candidates):
        if perf_counter()>=deadline:break
        point=v[point_id]
        anchored[point_id]=np.any((parent[:,0]==point[0])&(parent[:,1]==point[1])&(parent[:,2]==point[2]))
    order=np.argsort(np.linalg.norm(v[candidates[:,0]]-v[candidates[:,1]],axis=1),kind='stable')
    live=np.ones(len(f),dtype=bool);preparation_ms=(perf_counter()-start)*1000
    for x,y in candidates[order]:
        if perf_counter()>=deadline or len(operations)>=max_collapses:break
        x,y=int(x),int(y)
        # 完全相同坐标的别名合并不移动父锚点；不同坐标的两个父锚点仍禁止收缩。
        if anchored[x] and anchored[y] and not np.array_equal(v[x],v[y]):rejections.append('两个父锚点');continue
        keep,drop=(x,y) if anchored[x] or not anchored[y] else (y,x)
        # 同样的三列成员判定，避免逐候选短轴归约开销。
        fx=live&((f[:,0]==keep)|(f[:,1]==keep)|(f[:,2]==keep))
        fy=live&((f[:,0]==drop)|(f[:,1]==drop)|(f[:,2]==drop));owners=np.flatnonzero(fx&fy)
        if len(owners)!=2:rejections.append('边不是闭合二流形');continue
        nx=set(f[fx].ravel())-{keep};ny=set(f[fy].ravel())-{drop}
        if nx&ny != set(f[owners].ravel())-{keep,drop}:rejections.append('链接条件');continue
        # 每个标签分别检查边界链接，禁止通过删除整个来源片消除细小特征。
        valid_labels=True
        for label in np.unique(labels[fx|fy]):
            lx=fx&(labels==label);ly=fy&(labels==label);le=np.flatnonzero(lx&ly)
            if not len(le):valid_labels=False;break
            if (set(f[lx].ravel())-{keep})&(set(f[ly].ravel())-{drop}) != set(f[le].ravel())-{keep,drop}:
                valid_labels=False;break
        if not valid_labels:rejections.append('来源边界链接');continue
        ds=sum((Fraction.from_float(float(v[keep,k]))-Fraction.from_float(float(v[drop,k])))**2 for k in range(3))
        if ds>Fraction.from_float(tolerance_mm)**2:rejections.append('准确位移界');continue
        upper=nextafter(sqrt(float(ds)),inf) if ds else 0.0
        while Fraction.from_float(upper)**2<ds:upper=nextafter(upper,inf)
        affected=np.flatnonzero(fy);proposed=f[affected].copy();proposed[proposed==drop]=keep
        survives=np.array([len(set(t))==3 for t in proposed]);removed=affected[~survives]
        other=live.copy();other[affected]=False
        retained=np.vstack((f[other],proposed[survives]));retained_labels=np.concatenate((labels[other],labels[affected[survives]]))
        coverage=[];covered=True
        for face_id,tri in zip(removed,proposed[~survives]):
            label=labels[face_id];support=retained[retained_labels==label]
            points=sorted(set(map(int,tri)));image_edges=sorted({tuple(sorted((int(tri[k]),int(tri[(k+1)%3])))) for k in range(3) if tri[k]!=tri[(k+1)%3]})
            if any(not np.any(np.any(support==p,axis=1)) for p in points) or any(not np.any(np.any(support==a,axis=1)&np.any(support==b,axis=1)) for a,b in image_edges):
                covered=False;break
            coverage.append(dict(original_face=int(face_id),label=int(label),points=points,edges=image_edges))
        if not covered:rejections.append('退化映像缺少同标签覆盖');continue
        valid=True;checks=0
        for tri in proposed[survives]:
            points=v[tri];area=np.linalg.norm(np.cross(points[1]-points[0],points[2]-points[0]))/2
            if not np.isfinite(area) or area<=0:valid=False;break
            tl,th=points.min(0),points.max(0)
            # 全域障碍保持，逐列比较避免全网格三列归约，和原重叠集合逐项相同。
            overlaps=np.flatnonzero(other&(high[:,0]>=tl[0])&(high[:,1]>=tl[1])&(high[:,2]>=tl[2])&
                (low[:,0]<=th[0])&(low[:,1]<=th[1])&(low[:,2]<=th[2]))
            for face_id in overlaps:
                checks+=1
                if perf_counter()>=deadline or not separation_check(v,list(tri),list(f[face_id]),deadline):valid=False;break
            if not valid:break
        # 新星形面之间也检查，不能只看新面与静止外部。
        new=proposed[survives]
        for i in range(len(new)):
            if not valid:break
            for j in range(i):
                checks+=1
                if perf_counter()>=deadline or not separation_check(v,list(new[i]),list(new[j]),deadline):valid=False;break
        if not valid:rejections.append('无法证明替换星形面分离或预算耗尽');continue
        if perf_counter()>=deadline:break
        f[affected]=proposed;live[removed]=False
        if len(new):low[affected[survives]]=v[new].min(1);high[affected[survives]]=v[new].max(1)
        operations.append(dict(keep=keep,drop=drop,kept_parent_anchor=bool(anchored[keep]),
            changed_original_faces=affected.tolist(),removed_original_faces=removed.tolist(),coverage=coverage,
            distance_squared_numerator=str(ds.numerator),distance_squared_denominator=str(ds.denominator),
            geometry_upper_mm=upper,separation_checks=checks))
    # 按准确分数累计每项向外距离上界，避免浮点求和低估整批改变量。
    exact_total=sum((Fraction.from_float(o['geometry_upper_mm']) for o in operations),Fraction(0))
    total_bound=float(exact_total)
    while Fraction.from_float(total_bound)<exact_total:total_bound=nextafter(total_bound,inf)
    result=dict(budget_ms=budget_ms,preparation_ms=preparation_ms,candidate_edges=len(candidates),
        operations=operations,rejections=rejections,surviving_original_faces=np.flatnonzero(live).tolist(),
        source_whole_embedding_not_proven=True,vertices_unchanged=True,geometry_upper_sum_mm=total_bound,
        sum_of_outward_bounds_numerator=str(exact_total.numerator),sum_of_outward_bounds_denominator=str(exact_total.denominator))
    # 返回面和标签的数组复制也计入预算；不能把返回表达式的复制留在时钟之外。
    output_faces=f[live];output_labels=labels[live]
    result['total_elapsed_ms']=(perf_counter()-start)*1000;result['budget_overrun']=result['total_elapsed_ms']>budget_ms
    return v,output_faces,output_labels,result
