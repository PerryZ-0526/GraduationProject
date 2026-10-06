"""用绑定保存网格的精确实体分类替代过于保守的包围盒锚点限制。"""

from fractions import Fraction
from pathlib import Path
import json

import numpy as np

from audit_followup_candidate import sha256
from locality_masks import save_obj_fp64
from run_geometry_study import execute


class ExactCutSide:
    def __init__(self, engine, executable):
        self.engine = engine
        self.executable = executable
        self.counter = 0

    def classify(self, mesh, points):
        self.counter += 1
        mesh_path = self.engine.output / f"side_{self.counter}.obj"
        points_path = self.engine.output / f"side_{self.counter}.txt"
        save_obj_fp64(mesh, mesh_path)
        np.savetxt(points_path, points, fmt="%.17g")
        for path in (mesh_path, points_path):
            remote = self.engine.remote + "/" + path.name
            self.engine.sftp.put(str(path), remote)
            if execute(self.engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
                raise ValueError("精确侧分类输入摘要不匹配")
        run = execute(self.engine.client, [self.executable, self.engine.remote + "/" + mesh_path.name,
                                         self.engine.remote + "/" + points_path.name], timeout=120)
        if run["returncode"]:
            return {"embedded_closed": False, "sides": [], "execution": run}
        return {**json.loads(run["stdout"]), "saved_mesh_sha256": sha256(mesh_path),
                "points_sha256": sha256(points_path), "execution": run}

    def anchor(self, mesh, tool, normals, offsets):
        center = tool.vertices.mean(axis=0)
        candidates = [center]
        for axis in range(3):
            for extreme in (np.argmin(tool.vertices[:, axis]), np.argmax(tool.vertices[:, axis])):
                candidates.append(.999 * tool.vertices[extreme] + .001 * center)
        # 先精确核对工具排斥域内部，再对候选点做实体分类，不能以材料外点替代工具内部锚点。
        exact_normals = [tuple(Fraction(float(x)) for x in normal) for normal in normals]
        interior = []
        for point in candidates:
            exact = tuple(Fraction(float(x)) for x in point)
            if all(sum(a * b for a, b in zip(n, exact)) < Fraction(float(offset))
                   for n, offset in zip(exact_normals, offsets)):
                interior.append(point)
        if not interior:
            return {"passed": False, "reason": "no_strict_tool_interior_anchor"}
        result = self.classify(mesh, interior)
        if result["embedded_closed"]:
            for point, side in zip(interior, result["sides"]):
                if side == -1:
                    return {"passed": True, "point_mm": point.tolist(), "side": side, "classification": result,
                            "scope": "严格在工具支撑交集内、在已存储闭合嵌入骨材料外；结合整面支撑才推出材料排斥"}
        return {"passed": False, "reason": "no_exact_material_outside_anchor", "classification": result}
