"""使用同一精度分类距离的完整碰撞求解，继续保留原异常和诊断。"""
from collision_diff_diagnostic import CollisionProtectedSystem as DiagnosticSystem
from precision_collision_install import install_precision_collision


class CollisionProtectedSystem(DiagnosticSystem):
    def __init__(self,config):
        self.precision_install=install_precision_collision()
        super().__init__(config)
