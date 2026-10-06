"""用同一FP64最近点权重计算距离梯度，返回作者原FP32梯度结构。"""
import warp as wp
from robust_pt_gpu import double_point
from pamo_safe_project.kernels.distance_kernels.grad_funcs_struct import Dd_dx


@wp.func
def narrow_vector(x:wp.vec3d):
    return wp.vec3(wp.float32(x[0]),wp.float32(x[1]),wp.float32(x[2]))


@wp.func
def robust_pt_gradient_struct(x0:wp.vec3,x1:wp.vec3,x2:wp.vec3,x3:wp.vec3,kind:int):
    p=double_point(x0)
    a=double_point(x1)
    b=double_point(x2)
    c=double_point(x3)
    weights=wp.vec3d(wp.float64(0.0))
    closest=a
    if kind==0:
        normal=wp.cross(b-a,c-a)
        area=wp.dot(normal,normal)
        closest=p-normal*(wp.dot(p-a,normal)/area)
        weights[0]=wp.dot(wp.cross(b-closest,c-closest),normal)/area
        weights[1]=wp.dot(wp.cross(c-closest,a-closest),normal)/area
        weights[2]=wp.dot(wp.cross(a-closest,b-closest),normal)/area
    elif kind==1:
        weights[0]=wp.float64(1.0)
        closest=a
    elif kind==2:
        weights[1]=wp.float64(1.0)
        closest=b
    elif kind==4:
        weights[2]=wp.float64(1.0)
        closest=c
    else:
        first=0
        last=1
        start=a
        end=b
        if kind==6:
            first=1
            last=2
            start=b
            end=c
        elif kind==5:
            first=2
            last=0
            start=c
            end=a
        direction=end-start
        parameter=wp.dot(p-start,direction)/wp.dot(direction,direction)
        closest=start+parameter*direction
        weights[first]=wp.float64(1.0)-parameter
        weights[last]=parameter
    delta=p-closest
    # 真正零距离不人为赋零梯度；保留除零产生的非有限值，由原求解规则拒绝。
    gradient=delta/wp.sqrt(wp.dot(delta,delta))
    result=Dd_dx()
    result.d0=narrow_vector(gradient)
    result.d1=narrow_vector(-weights[0]*gradient)
    result.d2=narrow_vector(-weights[1]*gradient)
    result.d3=narrow_vector(-weights[2]*gradient)
    return result


@wp.func
def robust_pt_gradient_array(x0:wp.vec3,x1:wp.vec3,x2:wp.vec3,x3:wp.vec3,gradient:wp.array(dtype=wp.vec3),kind:int):
    value=robust_pt_gradient_struct(x0,x1,x2,x3,kind)
    gradient[0]=value.d0
    gradient[1]=value.d1
    gradient[2]=value.d2
    gradient[3]=value.d3
