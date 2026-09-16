"""恢复计划所需的交集、差集解析检查，不只检查进程返回码。"""
import tempfile
import argparse
from pathlib import Path
import numpy as np
import trimesh
from coverage_baseline import boolean
import coverage_baseline
from run_comparison import export_double


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-simplify',action='store_true')
    if parser.parse_args().no_simplify:
        coverage_baseline.BINARY='/root/autodl-tmp/graduation_project/cuda_stage0/geogram_plan_nosimplify'
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary)
        a=trimesh.creation.box(extents=[2,2,2])
        b=a.copy()
        b.apply_translation([1,0,0])
        paths=[folder/f'{name}.obj' for name in ['a','b','out']]
        paths[0].write_text(export_double(a))
        paths[1].write_text(export_double(b))
        for intersection in [False,True]:
            result=boolean(*paths,intersection=intersection)
            assert result.is_watertight and result.is_winding_consistent
            np.testing.assert_allclose(result.volume,4,atol=1e-10,rtol=0)
    print('解析交集与差集：2项通过')
