"""核对作者源码并隔离构建原样与邻接排序两个简化扩展。"""

import argparse
import json
from pathlib import Path
import shutil

from run_reference_cut_feedback import ReferenceCutEngine
from run_geometry_study import execute, PYTHON, save, now, retrieve
from audit_followup_candidate import sha256


AUTHOR = "/root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/pamo/simp_cuda/src"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，构建原样及单一排序对照",
              "文档概述": "不替换作者安装，排序假设尚未证明", "索引目录": ["source", "builds"],
              "status": "running", "source": {}, "builds": []}
    record = args.output / "01-简化邻接顺序隔离构建.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise RuntimeError("隔离目录已存在")
        original = args.output / "作者源码"
        original.mkdir()

        def download(remote, local):
            # 只取作者源码目录，逐文件记录实际摘要，不读取凭据。
            for entry in engine.sftp.listdir_attr(remote):
                import stat
                dst = local / entry.filename
                src = remote + "/" + entry.filename
                if stat.S_ISDIR(entry.st_mode):
                    dst.mkdir()
                    download(src, dst)
                else:
                    engine.sftp.get(src, str(dst))
                    digest = execute(engine.client, ["sha256sum", src])["stdout"].split()[0]
                    if digest != sha256(dst):
                        raise ValueError("作者源码取回摘要不一致")
                    report["source"][str(dst.relative_to(original))] = digest

        download(AUTHOR, original)
        kernel = """
    // 对每个顶点的邻接面编号排序，固定浮点求和顺序；不增删邻接成员。
    __global__ void sort_near_tris_kernel(CUSimp_Free sp)
    {
        int vertex = blockIdx.x * blockDim.x + threadIdx.x;
        if (vertex >= sp.n_pts) return;
        int first = sp.first_near_tris[vertex];
        int last = sp.first_near_tris[vertex + 1];
        for (int i = first + 1; i < last; ++i) {
            int value = sp.near_tris[i];
            int j = i - 1;
            while (j >= first && sp.near_tris[j] > value) {
                sp.near_tris[j + 1] = sp.near_tris[j];
                --j;
            }
            sp.near_tris[j + 1] = value;
        }
    }

"""
        for variant in ("control", "sorted"):
            directory = args.output / variant
            shutil.copytree(original, directory / "src")
            if variant == "sorted":
                path = directory / "src/cusimp_free.cu"
                text = path.read_text("utf8")
                anchor = "    __global__ void compute_vert_Q_kernel(CUSimp_Free sp)"
                call = "        create_near_tris_kernel<<<(n_tris + BLOCK_SIZE - 1) / BLOCK_SIZE, BLOCK_SIZE>>>(*this);"
                if text.count(anchor) != 1 or text.count(call) != 1:
                    raise ValueError("排序源码锚点不唯一")
                text = text.replace(anchor, kernel + anchor).replace(call, call + "\n        // 同一流中等待邻接填充后排序，再执行作者后续步骤。\n        sort_near_tris_kernel<<<(n_pts + BLOCK_SIZE - 1) / BLOCK_SIZE, BLOCK_SIZE>>>(*this);")
                path.write_text(text, "utf8")
            remote = engine.remote + "/" + variant
            execute(engine.client, ["mkdir", "-p", remote + "/src/bvh", remote + "/build"])
            hashes = {}
            for path in (directory / "src").rglob("*"):
                if path.is_file():
                    name = str(path.relative_to(directory)).replace("\\", "/")
                    engine.sftp.put(str(path), remote + "/" + name)
                    hashes[name] = sha256(path)
                    if execute(engine.client, ["sha256sum", remote + "/" + name])["stdout"].split()[0] != hashes[name]:
                        raise ValueError("构建源码上传摘要不符")
            module = "pamo_order_" + variant
            builder = Path(__file__).with_name("build_locality_cuda.py").read_text("utf8").replace('name="pamo_locality_cuda"', 'name="' + module + '"')
            local_builder = directory / "builder.py"
            local_builder.write_text(builder, "utf8")
            engine.sftp.put(str(local_builder), remote + "/builder.py")
            row = {"variant": variant, "source_sha256": hashes, "builder_sha256": sha256(local_builder), "module": module}
            report["builds"].append(row)
            save(record, report)
            row["execution"] = execute(engine.client, ["env", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6", PYTHON,
                                    remote + "/builder.py", "--directory", remote], remote + "/build.log", timeout=600)
            retrieve(engine.client, engine.sftp, remote + "/build.log", directory / "build.log")
            if row["execution"]["returncode"]:
                save(record, report)
                raise RuntimeError("隔离扩展编译失败，见日志")
            row["extension"] = remote + "/build/" + module + ".so"
            row["extension_sha256"] = execute(engine.client, ["sha256sum", row["extension"]])["stdout"].split()[0]
            save(record, report)
            print(variant, "built", flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
