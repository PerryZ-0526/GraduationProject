"""在真实CUDA核上核对固定常量能量、真零拒绝、速度拒绝及混合接触不变。"""
import argparse
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import warp as wp
from precision_gradient_install import install_precision_gradient
from preserved_collision_install import install_preserved_calculators


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries",type=Path,required=True)
    parser.add_argument("--binding",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    wp.init()
    install_precision_gradient()
    import pamo_safe_project.energy as author
    data = np.load(args.queries)
    binding = json.loads(args.binding.read_text(encoding="utf-8"))
    scale = binding["normalization_scale"]
    translation = np.asarray(binding["normalization_translation"])
    points = data["points"]
    count = len(points)
    n = 4*count
    config = SimpleNamespace(max_blocks=count,coll_stiffness=100.0,d_hat=.001,
        ee_classify_thres=.001,ccd_slackness=.7,ccd_thickness=1e-6,ccd_max_iters=100)
    system = SimpleNamespace(device="cuda:0",config=config,
        original_fixed_mask=wp.array(np.ones(n,dtype=np.int32),dtype=int,device="cuda:0"),
        original_fixed_mm=wp.array(points.reshape(-1,3),dtype=wp.vec3d,device="cuda:0"),
        geometry_scale=np.float64(scale),geometry_failures=wp.zeros(2,dtype=int,device="cuda:0"))
    x = wp.array((points.reshape(-1,3)*scale+translation).astype(np.float32),dtype=wp.vec3,device="cuda:0")
    indices = np.arange(n,dtype=np.int32).reshape(-1,4)
    types = np.zeros((count,2),np.int32)
    types[:,0] = data["types"]
    calculator = SimpleNamespace(system=system,contact_counter=wp.array(np.array([84],np.int32),dtype=int,device="cuda:0"),
        block_types=wp.array(types,dtype=int,device="cuda:0"),block_indices=wp.array(indices,dtype=int,device="cuda:0"),
        d=wp.zeros(count,dtype=float,device="cuda:0"),dd_dx=wp.zeros((count,4),dtype=wp.vec3,device="cuda:0"))
    key = type("CollisionBvhEnergyCalculator",(),{})
    system.energy_calcs = {key:calculator}
    install_preserved_calculators(system)
    energy = wp.zeros(1,dtype=float,device="cuda:0")
    grad = wp.zeros(n,dtype=wp.vec3,device="cuda:0")
    diag = wp.zeros(n,dtype=wp.vec3,device="cuda:0")
    dx = wp.array(np.arange(n*3,dtype=np.float32).reshape(n,3)/100.0,dtype=wp.vec3,device="cuda:0")
    hess = wp.zeros(n,dtype=wp.vec3,device="cuda:0")
    velocity = wp.zeros(n,dtype=wp.vec3,device="cuda:0")
    step = wp.array(np.array([1.0],np.float32),dtype=float,device="cuda:0")
    calculator.compute_energy(x,energy)
    calculator.compute_diff(x,-1.0,grad,diag)
    calculator.compute_hess_dx(x,dx,hess)
    calculator.ccd(x,velocity,step)
    actual = float(energy.numpy()[0])
    distances = (data["reference"][:84]*scale).astype(np.float32).astype(float)
    expected = float(np.sum(np.where(distances < config.d_hat,
        -(distances-config.d_hat)**2*np.log(distances/config.d_hat)*config.coll_stiffness,0)))
    positive = dict(queries=84,energy_finite=bool(np.isfinite(actual)),energy=actual,reference_energy=expected,
        energy_relative_error=abs(actual-expected)/abs(expected),failure_flags=system.geometry_failures.numpy().tolist(),
        constrained_gradient_zero=bool(not grad.numpy().any()),constrained_hessian_zero=bool(not hess.numpy().any()),
        cached_derivatives_zero=bool(not calculator.dd_dx.numpy().any()),ccd_step=float(step.numpy()[0]))
    # 增加四个真实零距离控制：能量和CCD两入口都必须保留拒绝标志。
    calculator.contact_counter.assign(np.array([count],np.int32))
    system.geometry_failures.zero_()
    calculator.compute_energy(x,energy)
    calculator.ccd(x,velocity,step)
    zero_flags = system.geometry_failures.numpy().tolist()
    # 固定接触若被错误赋予速度，必须拒绝而不能静默使用静态分支。
    calculator.contact_counter.assign(np.array([1],np.int32))
    system.geometry_failures.zero_()
    moving = np.zeros((n,3),np.float32)
    moving[0,0] = 1.0
    velocity.assign(moving)
    calculator.ccd(x,velocity,step)
    velocity_flags = system.geometry_failures.numpy().tolist()
    # 只放开一个点，逐数组核对仍走作者动态能量、导数、Hessian和CCD核体。
    physical = np.zeros((n,3),float)
    physical[:4] = [[.2,.2,.0001],[0,0,0],[1,0,0],[0,1,0]]
    x.assign(physical.astype(np.float32))
    mask = np.ones(n,np.int32)
    mask[0] = 0
    system.original_fixed_mask.assign(mask)
    system.geometry_failures.zero_()
    velocity.zero_()
    moving[0] = [0,0,-.0002]
    velocity.assign(moving)
    energy.zero_(); grad.zero_(); diag.zero_(); hess.zero_(); step.fill_(1.0)
    calculator.compute_energy(x,energy)
    calculator.compute_diff(x,-1.0,grad,diag)
    calculator.compute_hess_dx(x,dx,hess)
    calculator.ccd(x,velocity,step)
    observed = [item.numpy().copy() for item in (energy,grad,diag,hess,step)]
    energy.zero_(); grad.zero_(); diag.zero_(); hess.zero_(); step.fill_(1.0)
    wp.launch(author.collision_energy_kernel,count,inputs=[x,calculator.contact_counter,calculator.block_types,
        calculator.block_indices,config.coll_stiffness,config.d_hat,config.ee_classify_thres,calculator.d,energy],device="cuda:0")
    wp.launch(author.collision_diff_kernel,count,inputs=[x,calculator.contact_counter,calculator.block_types,
        calculator.block_indices,config.coll_stiffness,config.d_hat,calculator.d,-1.0,calculator.dd_dx,grad,diag],device="cuda:0")
    wp.launch(author.collision_hess_dx_kernel,count,inputs=[calculator.contact_counter,calculator.block_indices,
        calculator.d,config.coll_stiffness,config.d_hat,calculator.dd_dx,dx,hess],device="cuda:0")
    wp.launch(author.accd_kernel,count,inputs=[calculator.contact_counter,x,velocity,calculator.block_types,
        calculator.block_indices,config.ccd_slackness,config.ccd_thickness,config.ccd_max_iters,config.ee_classify_thres,step],device="cuda:0")
    baseline = [item.numpy().copy() for item in (energy,grad,diag,hess,step)]
    equality = [bool(np.array_equal(first,second)) for first,second in zip(observed,baseline)]
    finite = all(np.isfinite(item).all() for item in observed)
    passed = bool(positive["energy_finite"] and positive["energy_relative_error"] <= 1e-5
        and positive["failure_flags"] == [0,0] and positive["constrained_gradient_zero"]
        and positive["constrained_hessian_zero"] and positive["cached_derivatives_zero"]
        and positive["ccd_step"] == 1.0 and zero_flags == [8,0] and velocity_flags == [0,1]
        and all(equality) and finite and 0 < float(observed[-1][0]) < 1)
    result = dict(published=False,passed=passed,positive_fixed=positive,true_zero_flags=zero_flags,
        nonzero_fixed_velocity_flags=velocity_flags,mixed_contact_exact_array_equal=equality,
        mixed_finite=bool(finite),mixed_ccd_step=float(observed[-1][0]),scope="冻结微批及一个混合运动控制，不是全域CCD证书")
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
