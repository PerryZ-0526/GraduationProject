"""在隔离副本中为固定PaMO源码加入同步阶段计时，不改变算法条件。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_NORMALIZED_SHA256 = "389865cbfebd13f63bd154497c980368840b5d771576cde49f15fea98df498ca"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(content: str, old: str, new: str) -> str:
    if content.count(old) != 1:
        raise ValueError(f"计时插入锚点不唯一或源码版本变化: {old[:48]}")
    return content.replace(old, new)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    if destination.exists():
        raise ValueError("隔离目标已存在，禁止覆盖")
    original = source.read_bytes().replace(b"\r\n", b"\n")
    if sha256(original) != EXPECTED_NORMALIZED_SHA256:
        raise ValueError("作者PaMO源码与固定计时适配版本不一致")
    content = original.decode("utf-8")
    content = replace_once(
        content,
        "            start_stage1 = time.time()\n            verts, faces = self.remesh(tris, tris_min, tris_max, tris_mean)\n            end_stage1 = time.time()",
        "            torch.cuda.synchronize()\n            # 观察性同步计时：阶段一包含作者原有的主机与设备转换。\n            sync_start_stage1 = time.perf_counter()\n            start_stage1 = time.time()\n            verts, faces = self.remesh(tris, tris_min, tris_max, tris_mean)\n            torch.cuda.synchronize()\n            sync_end_stage1 = time.perf_counter()\n            end_stage1 = time.time()\n            print(f\"SYNC_STAGE1_MS: {(sync_end_stage1 - sync_start_stage1) * 1000.0}\")",
    )
    content = replace_once(
        content,
        "        start_stage2 =time.time()",
        "        torch.cuda.synchronize()\n        # 阶段二起点与阶段一相邻，结束时等待结果拷回主机。\n        sync_start_stage2 = time.perf_counter()\n        start_stage2 =time.time()",
    )
    content = replace_once(
        content,
        "        end_stage2 = time.time()\n        verts = verts.cpu().numpy()+ tris_mean\n        faces = faces.cpu().numpy()",
        "        verts = verts.cpu().numpy()+ tris_mean\n        faces = faces.cpu().numpy()\n        torch.cuda.synchronize()\n        sync_end_stage2 = time.perf_counter()\n        end_stage2 = time.time()\n        print(f\"SYNC_STAGE2_MS: {(sync_end_stage2 - sync_start_stage2) * 1000.0}\")",
    )
    content = replace_once(
        content,
        "        if self.use_stage3 == True:\n            stage2_mesh = trimesh.Trimesh(vertices=verts, faces=faces)",
        "        if self.use_stage3 == True:\n            torch.cuda.synchronize()\n            # 阶段三返回主机数组后再次同步，单列安全投影墙钟。\n            sync_start_stage3 = time.perf_counter()\n            stage2_mesh = trimesh.Trimesh(vertices=verts, faces=faces)",
    )
    content = replace_once(
        content,
        "                config=self.config,  # if system is not provided, use this config to create a new system\n            )",
        "                config=self.config,  # if system is not provided, use this config to create a new system\n            )\n            torch.cuda.synchronize()\n            sync_end_stage3 = time.perf_counter()\n            print(f\"SYNC_STAGE3_MS: {(sync_end_stage3 - sync_start_stage3) * 1000.0}\")",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8", newline="\n")
    record = {"source_sha256_normalized": EXPECTED_NORMALIZED_SHA256,
              "destination_sha256": sha256(destination.read_bytes()),
              "interpretation": "隔离观察版本；阶段同步墙钟与完整进程墙钟分列，非GPU事件计时"}
    destination.with_suffix(".timing.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
