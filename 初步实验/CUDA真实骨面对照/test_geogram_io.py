"""检查Geogram适配器的双精度往返与解析立方体差集体积。"""
from pathlib import Path
import subprocess
import tempfile
import numpy as np
import trimesh
from run_comparison import face_keys, export_double
from experiment import load_candidate


if __name__ == '__main__':
    exe = '/root/autodl-tmp/graduation_project/cuda_stage0/geogram_double_io'
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        candidate, _ = load_candidate()
        a, b, out = [folder/name for name in ['a.obj','b.obj','out.obj']]
        a.write_text(export_double(candidate['whole']))
        subprocess.run([exe, '--copy', str(a), str(out)], check=True)
        observed = trimesh.load(out, force='mesh', process=False)
        assert set(face_keys(observed)) == set(face_keys(candidate['whole']))
        first = trimesh.creation.box(extents=[2,2,2])
        second = first.copy()
        second.apply_translation([1,0,0])
        a.write_text(export_double(first))
        b.write_text(export_double(second))
        subprocess.run([exe,str(a),str(b),str(out)], check=True)
        observed = trimesh.load(out, force='mesh', process=False)
        assert observed.is_watertight and observed.is_winding_consistent
        np.testing.assert_allclose(observed.volume, 4., rtol=0, atol=1e-10)
    print('双精度整骨往返与解析差集：2项通过')
