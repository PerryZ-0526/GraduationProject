"""人工盒体包住凸工具的负例：面支撑通过也不能省略材料侧锚点。"""

import getpass
import json
import os
from pathlib import Path

import trimesh
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, save, now
from cut_side_classifier import ExactCutSide
from audit_followup_candidate import sha256
from locality_masks import save_obj_fp64
from strict_no_change_reuse import try_strict_no_change_reuse


def main():
    project = Path.cwd()
    cfg = dict(line.split("=", 1) for line in (project / ".env").read_text("utf8").splitlines() if line and not line.startswith("#"))
    getpass.getpass = lambda _: cfg["CUDA_SSH_PASSWORD"]
    os.environ["GPU_SSH_HOST"] = "connect.westb.seetacloud.com"
    # 两个薄壁工具都同时触发面支撑拒绝；另存解析盒体以单独验证材料侧。
    output = Path("D:/GraduationProject_切削排斥证据/20261005_严格复用包围凸工具盒体负例")
    output.mkdir(exist_ok=False)
    # 严格相同的解析盒体源仅用于认证器负例，不冒充实际Geogram布尔结果。
    parent = source = output / "parent.obj"
    material = trimesh.creation.box(extents=[2., 2., 2.])
    save_obj_fp64(material, parent)
    labels = output / "labels.json"
    save(labels, {"operand_bits": [1] * len(material.faces)})
    tool = trimesh.creation.icosphere(subdivisions=1, radius=.1)
    tool_path = output / "01-材料内部人工凸工具.obj"
    save_obj_fp64(tool, tool_path)
    engine = RemoteQuality(output, 51667)
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("负例远端目录已存在")
        validation_path = project / "初步实验/Geogram与PaMO组合验证/实验结果/20261004_切削排斥精确材料侧分类开发/01-精确侧分类器与骨面锚点验证.json"
        validation = json.loads(validation_path.read_text("utf8"))["environment"]
        if execute(engine.client, ["sha256sum", validation["executable"]])["stdout"].split()[0] != validation["executable_sha256"]:
            raise ValueError("精确侧分类器已变化")
        engine.side = ExactCutSide(engine, validation["executable"])
        result = try_strict_no_change_reuse(engine, parent, source, labels, [tool_path], output / "negative_candidate")
        assert result["identity"]["same"]
        assert result["cumulative_tools"][0]["face_support"]["passed"]
        assert not result["cumulative_tools"][0]["material_side"]["passed"]
        assert result["status"] == "strict_reuse_legality_rejected"
        save(output / "02-材料侧必需性负例核查.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，人工材料内部工具负例",
             "文档概述": "有向表面严格相同及整面排斥并不足以保证工具未被材料包住；材料侧检查必须拒绝",
             "索引目录": ["summary", "inputs"], "summary": {"passed": True, "full_GPU_calls": 0},
             "inputs": {"parent_sha256": sha256(parent), "source_sha256": sha256(source), "labels_sha256": sha256(labels), "tool_sha256": sha256(tool_path)},
             "result": result, "role": "artificial_certifier_negative_not_actual_boolean_event"})
        print("material_inside_negative_passed", flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
