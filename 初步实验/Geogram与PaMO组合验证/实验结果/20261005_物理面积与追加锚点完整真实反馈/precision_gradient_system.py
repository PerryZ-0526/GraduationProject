"""新梯度独立投影版本，不修改旧分类距离批次。"""
from all_contact_diff_diagnostic import CollisionProtectedSystem as DiagnosticSystem
from precision_gradient_install import install_precision_gradient


class CollisionProtectedSystem(DiagnosticSystem):
    def __init__(self, config):
        self.precision_install = install_precision_gradient()
        super().__init__(config)
