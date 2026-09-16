"""白名单归档作者源码，通过既有连接入口记录隔离构建的实际障碍。"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "reference/近期强基线_20260908/RXMesh"
REMOTE_SCRIPT = ROOT / "初步实验/CUDA远程验证/remote.py"
STAMP = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
OUT = HERE / "实验结果" / STAMP
REMOTE = "/root/autodl-tmp/graduation_project/build_rxmesh_dynamic_" + STAMP


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    records = []

    def connect(name, *args):
        # 连接配置仅由既有remote.py读取；本程序不读取或归档凭据。
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(REMOTE_SCRIPT), *args],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8",
            timeout=180, check=False,
        )
        (OUT / (name + ".log")).write_text(result.stdout, encoding="utf-8")
        records.append({"step": name, "arguments": list(args), "exit_code": result.returncode})
        print(name, result.returncode, result.stdout[-2500:], flush=True)
        return result.returncode

    commit = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", str(SOURCE), "status", "--short"], text=True)
    tracked = subprocess.check_output(["git", "-C", str(SOURCE), "ls-files", "-z"]).decode().split("\0")
    # 仅包含构建脚本、库源码、作者应用及一个输入；不递归打包项目或.git。
    files = [name for name in tracked if name in {"CMakeLists.txt", "LICENSE", "README.md", "input/cloth.obj"}
             or name.startswith(("cmake/", "include/", "apps/"))]
    manifest = []
    archive = OUT / "rxmesh_source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name in files:
            path = SOURCE / name
            if path.is_symlink() or not path.is_file():
                raise RuntimeError("白名单含非普通文件：" + name)
            data = path.read_bytes()
            manifest.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            bundle.add(path, arcname="source/" + name, recursive=False)
    summary = {"time_beijing": STAMP, "upstream_commit": commit, "upstream_status_before": status,
               "remote_directory": REMOTE, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
               "files": manifest, "commands": records, "gpu_dynamic_operation_executed": False}
    try:
        if connect("01_environment", "--command", "export PATH=/usr/local/cuda/bin:/root/miniconda3/bin:$PATH; "
                   "TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S'; cmake --version; nvcc --version; g++ --version; "
                   "nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv"):
            return
        if connect("02_create", "--command", "mkdir " + shlex.quote(REMOTE)):
            return
        if connect("03_upload", "--put", str(archive), REMOTE + "/rxmesh_source.tar.gz"):
            return
        if connect("04_unpack", "--command", "cd " + shlex.quote(REMOTE)
                   + " && sha256sum rxmesh_source.tar.gz && tar -xzf rxmesh_source.tar.gz"):
            return
        command = ("cd " + shlex.quote(REMOTE) + "; export PATH=/usr/local/cuda/bin:/root/miniconda3/bin:$PATH; "
                   "export TZ=Asia/Shanghai OMP_NUM_THREADS=4; "
                   "timeout 90s cmake -S source -B build -DCMAKE_BUILD_TYPE=Release "
                   "-DCMAKE_CUDA_ARCHITECTURES=89 -DRX_USE_POLYSCOPE=OFF -DRX_BUILD_TESTS=OFF "
                   "-DRX_BUILD_APPS=ON -DRX_USE_CUDSS=OFF -DRX_USE_SUITESPARSE=OFF "
                   "-DRX_USE_DOUBLE=OFF > configure.log 2>&1; rc=$?; cat configure.log; exit $rc")
        summary["configure_exit_code"] = connect("05_configure", "--command", command)
        # 本次只执行版本阻碍复现，避免新版环境中意外进入未经核验的构建步骤。
        summary["status"] = "configure_failed" if summary["configure_exit_code"] else "configured_not_built"
        connect("06_alternative_cmake", "--command",
                "find /root/miniconda3 /usr/local /opt /root/autodl-tmp/graduation_project "
                "-maxdepth 7 -type f -name cmake 2>/dev/null")
    finally:
        summary["upstream_status_after"] = subprocess.check_output(
            ["git", "-C", str(SOURCE), "status", "--short"], text=True)
        (OUT / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print("证据目录：", OUT, flush=True)


if __name__ == "__main__":
    main()
