"""复用回滚与缓冲区测试，并检查CUDA解析驻点与相切输入。"""
import unittest
import numpy as np
from cuda_device import CudaDevice
from test_integrated import IntegratedTests


class CudaTests(IntegratedTests):
    @classmethod
    def setUpClass(cls):
        cls.device = CudaDevice()

    def test_analytic(self):
        xy = np.array([[0., 0.], [3., 0.], [3.+1e-8, 0.], [0., 3.-1e-8]])
        tools = np.array([[0., 0., 0., 0., 3., 2.5]]*2)
        result = self.device.evaluate(xy, np.full(4, 4.), tools)
        expected = [-.5, 2.5, 4., 2.5-np.sqrt(9.-(3.-1e-8)**2)]
        np.testing.assert_allclose(result, expected, rtol=0., atol=1e-10)

    def test_changed_faces(self):
        import trimesh
        from run_comparison import quality, face_keys
        mesh = trimesh.creation.icosphere(subdivisions=1)
        keys = set(face_keys(mesh))
        self.assertEqual(quality(mesh, keys)['changed_faces'], 0)
        mesh.vertices[0, 2] += .01
        self.assertGreater(quality(mesh, keys)['changed_faces'], 0)


if __name__ == '__main__':
    # 只运行CUDA子类，避免测试发现机制启动Intel OpenCL父类。
    unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CudaTests)).wasSuccessful() or exit(1)
