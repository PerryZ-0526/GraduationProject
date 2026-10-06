"""FP32坐标上用FP64叉积分类与距离计算，不设置距离下限或删接触。"""
import warp as wp


@wp.struct
class SegmentCandidate:
    square: wp.float64
    kind: int


@wp.func
def double_point(x:wp.vec3):
    return wp.vec3d(wp.float64(x[0]),wp.float64(x[1]),wp.float64(x[2]))


@wp.func
def segment_candidate(p:wp.vec3d,a:wp.vec3d,b:wp.vec3d,edge:int,first:int,last:int):
    direction=b-a
    denominator=wp.dot(direction,direction)
    t=wp.float64(0.0)
    if denominator>wp.float64(0.0):
        t=wp.clamp(wp.dot(p-a,direction)/denominator,wp.float64(0.0),wp.float64(1.0))
    delta=p-(a+t*direction)
    result=SegmentCandidate()
    result.square=wp.dot(delta,delta)
    result.kind=edge
    if t<=wp.float64(0.0):
        result.kind=first
    elif t>=wp.float64(1.0):
        result.kind=last
    return result


@wp.func
def robust_pt_classify(x0:wp.vec3,x1:wp.vec3,x2:wp.vec3,x3:wp.vec3):
    p=double_point(x0)
    a=double_point(x1)
    b=double_point(x2)
    c=double_point(x3)
    normal=wp.cross(b-a,c-a)
    square=wp.dot(normal,normal)
    # 叉积边测试避免细长面的Gram行列式相减；FP64仍不是认证精确谓词。
    if square>wp.float64(0.0):
        first=wp.dot(wp.cross(b-a,p-a),normal)
        second=wp.dot(wp.cross(c-b,p-b),normal)
        third=wp.dot(wp.cross(a-c,p-c),normal)
        if first>=wp.float64(0.0) and second>=wp.float64(0.0) and third>=wp.float64(0.0):
            return 0
    ab=segment_candidate(p,a,b,3,1,2)
    bc=segment_candidate(p,b,c,6,2,4)
    ca=segment_candidate(p,c,a,5,4,1)
    best=ab
    if bc.square<best.square:
        best=bc
    if ca.square<best.square:
        best=ca
    return best.kind


@wp.func
def robust_pt_distance(x0:wp.vec3,x1:wp.vec3,x2:wp.vec3,x3:wp.vec3,kind:int):
    p=double_point(x0)
    a=double_point(x1)
    b=double_point(x2)
    c=double_point(x3)
    square=wp.float64(0.0)
    if kind==0:
        normal=wp.cross(b-a,c-a)
        numerator=wp.dot(p-a,normal)
        square=numerator*numerator/wp.dot(normal,normal)
    elif kind==1:
        square=wp.dot(p-a,p-a)
    elif kind==2:
        square=wp.dot(p-b,p-b)
    elif kind==4:
        square=wp.dot(p-c,p-c)
    elif kind==3:
        square=segment_candidate(p,a,b,3,1,2).square
    elif kind==6:
        square=segment_candidate(p,b,c,6,2,4).square
    elif kind==5:
        square=segment_candidate(p,c,a,5,4,1).square
    return wp.float32(wp.sqrt(square))
