"""逐步质量维护的回滚、回灌和双精度转换回归测试。"""
from unittest.mock import patch
import numpy as np
import trimesh
from dynamic_quality import DynamicQualityEngine, QualityRejected
from real_bone_system_demo import to_manifold, to_trimesh


def main():
    mesh = trimesh.creation.box()
    mesh.apply_translation([100.123456789, 100., 100.])
    result = to_trimesh(to_manifold(mesh, True), True)
    assert np.max(np.abs(np.sort(result.vertices, axis=0)-np.sort(mesh.vertices, axis=0))) < 1e-12
    engine = DynamicQualityEngine()
    old_mesh, old_volume = engine.current_mesh, engine.bone.volume()
    with patch('dynamic_quality.remesh_local', side_effect=ValueError('注入维护失败')):
        try:
            engine.step()
            raise AssertionError('失败状态不应被接受')
        except QualityRejected:
            pass
    assert engine.step_index == 0 and not engine.records
    assert engine.current_mesh is old_mesh and engine.bone.volume() == old_volume
    assert engine.blocked and not engine.attempts[-1]['accepted']
    engine.reset()
    assert not engine.blocked and not engine.attempts
    for _ in range(3):
        engine.step()
        assert engine.attempts[-1]['accepted']
        assert abs(engine.bone.volume()-engine.current_mesh.volume) < 1e-7
    assert engine.step_index == len(engine.records) == 3
    print('PASS: 双精度转换、失败原子回滚、重置、三步维护回灌')


if __name__ == '__main__':
    main()
