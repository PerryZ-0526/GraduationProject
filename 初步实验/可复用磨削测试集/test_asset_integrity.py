"""冻结资产摘要检查的缺失、冲突和跨包路径拒绝回归。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from audit_asset_integrity import check_package, digest


class AssetIntegrityTests(unittest.TestCase):
    def check(self, files, data=b"content"):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/"mesh.obj").write_bytes(data)
            manifest = root/"01-冻结清单.json"
            manifest.write_text(json.dumps(dict(files=files)), encoding="utf-8")
            return check_package(root, manifest)

    def test_matching_hash_and_repeated_reference(self):
        import hashlib
        row = dict(file="mesh.obj", sha256=hashlib.sha256(b"content").hexdigest())
        result = self.check([row, row])
        self.assertEqual(result["files"], 1)
        self.assertTrue(result["hashes_match"])

    def test_missing_or_changed_file_preserves_negative(self):
        for file in ("mesh.obj", "missing.obj"):
            result = self.check([dict(file=file, sha256="wrong")])
            self.assertFalse(result["hashes_match"])
            self.assertFalse(result["rows"][0]["passed"])

    def test_conflicting_hash_or_parent_path_rejected(self):
        for files in ([dict(file="mesh.obj", sha256="a"), dict(file="mesh.obj", sha256="b")],
                      [dict(file="../other.obj", sha256="a")]):
            with self.assertRaises(ValueError):
                self.check(files)

    def test_continuous_manifest_uses_initial_and_tools(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/"inputs").mkdir()
            path = root/"inputs/initial.obj"
            path.write_bytes(b"mesh")
            manifest = root/"01-完整范围冻结清单.json"
            manifest.write_text(json.dumps(dict(routes=[dict(initial_mesh="initial.obj", initial_mesh_sha256=digest(path),
                prefix_tools=[dict(mesh="initial.obj", sha256=digest(path))])])), encoding="utf-8")
            result = check_package(root, manifest)
            self.assertEqual(result["files"], 1)
            self.assertTrue(result["hashes_match"])


if __name__ == "__main__":
    unittest.main()
