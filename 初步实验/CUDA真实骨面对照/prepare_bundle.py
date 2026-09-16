"""只打包固定实验源码和公开骨面派生输入；不遍历凭据或全项目。"""
from pathlib import Path
import hashlib
import json
import tarfile
import argparse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--optimization', action='store_true')
    parser.add_argument('--coverage', action='store_true')
    args = parser.parse_args()
    names = {
        '局部区域重建阶段一': ['patch_model.py', 'test_patch.py'],
        '真实骨面高度图验证': ['projection.py', 'surface_patch.py', 'real_patch.py', 'test_projection.py'],
        '真实骨面共边拼接': ['stitch.py', 'test_stitch.py'],
        '边界过渡带联合重建': ['joint.py', 'dynamic.py', 'intersections.py', 'test_joint.py', '实验结果/joint.npz'],
        '局部适用域与核显计算': ['experiment.py', 'local_model.py', 'integrated.py', 'gpu_experiment.py', 'test_local.py', 'test_integrated.py'],
        '真实骨模型演示': ['real_bone_demo.py', 'scapula_hill_sachs_001_R.stl'],
        'CUDA真实骨面对照': ['cuda_device.py', 'sweep_cuda.cu', 'test_cuda.py', 'run_comparison.py', 'run_remote.sh', 'requirements.txt', 'geogram_double_io.cpp', 'test_geogram_io.py'],
    }
    hashes = {}
    # 各阶段快照另存，保留既有归档；始终使用显式白名单，不读取凭据。
    if args.optimization or args.coverage:
        names['CUDA真实骨面对照'] += ['incremental.py', 'resident_device.py', 'test_incremental.py',
            'test_resident.py', 'benchmark_incremental.py', 'interval_sweep.cu', 'interval_device.py',
            'test_interval.py', 'benchmark_interval.py', 'summarize_optimization.py']
    if args.coverage:
        names['CUDA真实骨面对照'] += ['coverage_inputs.py','coverage_cuda.py','coverage_baseline.py',
                                     'test_coverage.py','test_plan_boolean.py','summarize_coverage.py','maintenance_delta.py']
    archive_path = HERE/('coverage_sources.tar.gz' if args.coverage else 'optimization_sources.tar.gz' if args.optimization else 'stage1_sources.tar.gz')
    manifest_path = HERE/('coverage_source_hashes.json' if args.coverage else 'optimization_source_hashes.json' if args.optimization else 'source_hashes.json')
    with tarfile.open(archive_path, 'w:gz') as archive:
        for directory, files in names.items():
            for name in files:
                path = ROOT/'初步实验'/directory/name
                relative = path.relative_to(ROOT).as_posix()
                hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
                archive.add(path, arcname=relative)
    manifest_path.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding='utf-8')
    print(len(hashes), 'files', archive_path.stat().st_size, 'bytes')
