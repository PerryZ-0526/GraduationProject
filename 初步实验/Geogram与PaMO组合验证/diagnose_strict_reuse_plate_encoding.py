"""定位新同版板体第二刀实际编码交叠，保存同源面号及来源，暂不改拓扑。"""

import getpass
import json
import os
from pathlib import Path

import numpy as np
import trimesh
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256


def main():
    project = Path.cwd()
    root = Path("D:/GraduationProject_切削排斥证据")
    batch = root / "20261005_严格复用同版六家族18事件完整开发/板体_新参数1p4375_交叉"
    record = batch / "01-统一配置完整父反馈记录.json"
    row = json.loads(record.read_text("utf8"))["rows"][1]
    physical = batch / "板体_新参数1p4375_交叉_e1_candidate_input/clean_source.obj"
    labels = physical.with_name("clean_labels.json")
    encoded = batch / "e1_working_sources/01-CUDA初始编码源.obj"
    assert sha256(encoded) == row["actual_working_source_gate"]["checks"][0]["sha256"]
    cfg = dict(line.split("=", 1) for line in (project / ".env").read_text("utf8").splitlines() if line and not line.startswith("#"))
    getpass.getpass = lambda _: cfg["CUDA_SSH_PASSWORD"]
    os.environ["GPU_SSH_HOST"] = "connect.westb.seetacloud.com"
    output = root / "20261005_严格复用同版板体第二刀编码交叠定位"
    # 首次只读核查在JSON序列化处失败；允许同输入重新保存，已有完整诊断则禁止覆盖。
    output.mkdir(exist_ok=True)
    if (output / "01-板体物理合法但编码交叠逐面诊断.json").exists():
        raise ValueError("完整逐面诊断已保存")
    engine = RemoteQuality(output, 51667)
    try:
        assert execute(engine.client, ["mkdir", "-p", engine.remote])["returncode"] == 0
        checker = "/root/autodl-tmp/graduation_project/constrained_20261005_归一化精度候选与自交面号定位_f8be359dcba4/pairs"
        expected = "1537bebe89dfb2c2b2ab8a70b6331af3a02ec680a3d3b38d199f0ca7454c4127"
        assert execute(engine.client, ["sha256sum", checker])["stdout"].split()[0] == expected
        checks = []
        for name, path in (("physical", physical), ("actual_initial_encoded", encoded)):
            remote = engine.remote + "/" + name + ".obj"
            engine.sftp.put(str(path), remote)
            assert execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] == sha256(path)
            run = execute(engine.client, [checker, remote], timeout=120)
            assert run["returncode"] == 0
            checks.append({"source": name, "sha256": sha256(path), "execution": run, "embedding": json.loads(run["stdout"])})
        source = trimesh.load(physical, force="mesh", process=False)
        work = trimesh.load(encoded, force="mesh", process=False)
        assert np.array_equal(source.faces, work.faces)
        bits = json.loads(labels.read_text("utf8"))["operand_bits"]
        first = np.cross(source.triangles[:, 1] - source.triangles[:, 0], source.triangles[:, 2] - source.triangles[:, 0])
        second = np.cross(work.triangles[:, 1] - work.triangles[:, 0], work.triangles[:, 2] - work.triangles[:, 0])
        pairs = checks[1]["embedding"]["pair_face_ids_zero_based"]
        entries = [{"face_pair": pair, "source_bits": [bits[i] for i in pair],
                    "shared_vertices": [int(i) for i in sorted(set(source.faces[pair[0]]) & set(source.faces[pair[1]]))],
                    "physical_area_mm2": source.area_faces[pair].tolist(), "encoded_area_mm2": work.area_faces[pair].tolist(),
                    "physical_encoded_normal_dot": [float(first[i] @ second[i]) for i in pair]}
                   for pair in pairs]
        save(output / "01-板体物理合法但编码交叠逐面诊断.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，同实际保存工作源定位",
             "文档概述": "只读定位实际5对交叠，不修改原运行状态，不以法向局部判定替代完整嵌入",
             "索引目录": ["checks", "face_pairs"], "batch_sha256": sha256(record), "labels_sha256": sha256(labels),
             "checks": checks, "face_pairs": entries, "fixed_origin_mm": row["origin_mm"],
             "full_GPU_calls": 0, "new_geometry_certified": False})
        print(json.dumps(entries, ensure_ascii=False), flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
