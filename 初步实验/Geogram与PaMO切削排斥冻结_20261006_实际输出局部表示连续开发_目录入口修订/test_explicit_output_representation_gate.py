"""使用实际GPU正负例检验输出门控及证据摘要绑定。"""
from pathlib import Path
import json
import importlib.util
import unittest
import trimesh
import run_constrained_batch

# 冻结入口只将正式快照放在模块路径首位，本测试显式加载同目录新门控。
spec = importlib.util.spec_from_file_location('explicit_output_representation_gate', Path(__file__).with_name('explicit_output_representation_gate.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
audit_output_representation = module.audit_output_representation


class OutputRepresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path('D:/GraduationProject_切削排斥证据')
        cls.mesh = trimesh.load(root / '20261006_第六刀后排斥残留面积与编码定位/暂存面积处理候选.obj', process=False)
        cls.folder = root / '20261006_第六刀后排斥输出实际GPU局部表示核对_系统库入口修订'
        record = json.loads((root / '20261006_第六刀暂存输出显式局部表示六工具完整复审/01-显式局部表示的物理网格与六工具完整复审.json').read_text('utf8'))
        cls.certificate = record['physical_full_embedding']

    def test_tool_origin_accepts_actual_bound_representations(self):
        accepted, record = audit_output_representation(self.mesh, self.certificate, self.folder, 'tool')
        self.assertTrue(accepted)
        self.assertFalse(record['legacy_world_FP32_gate_accepted'])

    def test_world_encoding_rejects(self):
        self.assertFalse(audit_output_representation(self.mesh, self.certificate, self.folder, 'world')[0])

    def test_zero_degeneracy_alone_cannot_accept_intersections(self):
        self.assertFalse(audit_output_representation(self.mesh, self.certificate, self.folder, 'bad_faces_mean')[0])

    def test_mismatched_physical_certificate_rejects(self):
        certificate = {**self.certificate, 'saved_mesh_sha256': '0' * 64}
        self.assertFalse(audit_output_representation(self.mesh, certificate, self.folder, 'tool')[0])

    def test_changed_physical_mesh_rejects_old_GPU_evidence(self):
        changed = self.mesh.copy()
        changed.vertices[0, 0] += .01
        self.assertFalse(audit_output_representation(changed, self.certificate, self.folder, 'tool')[0])

    def test_absent_declared_origin_rejects(self):
        self.assertFalse(audit_output_representation(self.mesh, self.certificate, self.folder, 'absent')[0])


if __name__ == '__main__':
    unittest.main()
