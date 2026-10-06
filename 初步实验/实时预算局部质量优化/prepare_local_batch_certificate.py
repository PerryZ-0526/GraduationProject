"""冻结完整工具批更新，接入本机数组认证与共享质量拓扑，独立编译多操作数接口。"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


BASE = Path(__file__).resolve().parent
PARENT = Path('D:/GraduationProject实验输出')
ROOT = PARENT/'20261007_批更新自适应认证与本机质量完整验证'
SOURCE = PARENT/'20261007_自适应方向认证本机完整长轨迹'
GEOGRAM = PARENT/'20261007_数组源证书本机完整反馈'
ARCHIVE = PARENT/'20261007_五工具批量完整反馈_14137_v2/05-完整批量反馈与复审证据.zip'
CMAKE = 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    assert sha(ARCHIVE) == '59c6378ae8c93dc4f029da10bd7a225ecf5a378f1ff6a61e6a2efb9bbe00a3c0'
    frozen = json.loads((SOURCE/'00-完整长轨迹输入与本机方法冻结.json').read_text(encoding='utf-8'))
    for name, digest in frozen['files'].items():
        assert sha(SOURCE/name) == digest, name
    assert not ROOT.exists()
    ROOT.mkdir()
    master = ROOT/'workers'
    shutil.copytree(SOURCE/'workers', master)
    with zipfile.ZipFile(ARCHIVE) as archive:
        # 使用长期线路实际执行的批更新和来源编码规则；不根据本次结果临时改参数。
        names = ['resident_batch_engine.py', 'resident_batch_boolean_service.py', 'geogram_batch_memory.py', 'geogram_batch_memory.cpp',
                 'short_edge_repair.py', 'short_edge_repair_reference.py', 'covered_zero_cleanup.py', 'resident_source_cleanup.py']
        for name in names:
            (master/name).write_bytes(archive.read('workers/'+name))
        entry_text = archive.read('resident_batch_feedback_worker.py').decode('utf-8')
    engine = master/'resident_batch_engine.py'
    text = engine.read_text(encoding='utf-8')
    text = text.replace('from incremental_mesh_memory import VerifiedMesh', 'from certificate_activity_edges import SharedVerifiedMesh as VerifiedMesh')
    text = text.replace("max_flips=4,edge_backend='cuda')", "max_flips=4,edge_backend='cpu',certificate=self.certificate)")
    engine.write_text(text, encoding='utf-8')
    cpp = master/'geogram_batch_memory.cpp'
    text = cpp.read_text(encoding='utf-8')
    before='            GEO::Logger::instance()->set_quiet(true);initialized=true;'
    assert text.count(before) == 1
    text = text.replace(before, '            // 多操作数也显式登记唯一面扫描开关，不继承未声明的二操作数状态。\n'
                        '            GEO::CmdLine::declare_arg("algo:linear_unique_facets",false,"Linear unique triangle scan");\n'+before)
    before='        GEO::MeshSurfaceIntersection intersection(*result);'
    assert text.count(before) == 1
    text = text.replace(before, '        // 完整唯一性扫描成功才省排序；重复面仍走原作者处理。\n'
                        '        GEO::CmdLine::set_arg("algo:linear_unique_facets", "true");\n'+before)
    cpp.write_text(text, encoding='utf-8')
    # DLL与实际Geogram导入库须成对，不能链接另一线路可变的编译版本。
    import_library = GEOGRAM/'geogram_build/lib/Release/geogram.lib'
    geo_dll = GEOGRAM/'geogram_build/bin/Release/geogram.dll'
    assert sha(geo_dll) == sha(master/'geogram.dll')
    cmake_source = ROOT/'memory_source'
    cmake_source.mkdir()
    cmake = ['cmake_minimum_required(VERSION 3.20)', 'project(local_batch_certificate LANGUAGES CXX)',
             f'add_library(geogram_memory SHARED "{cpp.as_posix()}")', 'target_compile_features(geogram_memory PRIVATE cxx_std_17)',
             'target_compile_definitions(geogram_memory PRIVATE GEO_DYNAMIC_LIBS GEOGRAM_USE_BUILTIN_DEPS)',
             'target_compile_options(geogram_memory PRIVATE /utf-8)',
             f'target_include_directories(geogram_memory PRIVATE "{(GEOGRAM/"geogram_source/src/lib").as_posix()}")',
             f'target_link_libraries(geogram_memory PRIVATE "{import_library.as_posix()}")']
    (cmake_source/'CMakeLists.txt').write_text('\n'.join(cmake)+'\n', encoding='utf-8')
    for name, argv in [('configure', [CMAKE, '-S', str(cmake_source), '-B', str(ROOT/'memory_build'), '-G', 'Visual Studio 17 2022', '-A', 'x64']),
                       ('build', [CMAKE, '--build', str(ROOT/'memory_build'), '--config', 'Release', '--parallel', '2'])]:
        with (ROOT/(name+'.log')).open('x', encoding='utf-8') as log:
            code = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT).returncode
        assert code == 0, (name, code)
    shutil.copyfile(master/'geogram_memory.dll', master/'geogram_memory_single_original.dll')
    shutil.copyfile(ROOT/'memory_build/Release/geogram_memory.dll', master/'geogram_memory.dll')
    # 本机仅切换后端与渲染身份，所有实际到达、凑批等待和持久化费用保持测量。
    before='    import torch\n    startup=perf_counter();torch.cuda.init();torch.cuda.synchronize()\n    gpu=dict(device=torch.cuda.get_device_name(0),torch_version=torch.__version__,startup_ms=(perf_counter()-startup)*1000)'
    assert entry_text.count(before) == 1
    entry_text = entry_text.replace(before, "    # 本机维护不借用远端CUDA计时，实际Intel Arc渲染器在首帧核实。\n    gpu=dict(device='本机CPU维护；Intel Arc像素单列',startup_ms=0)")
    entry_text = entry_text.replace("if 'NVIDIA' not in renderer:", "if 'Intel' not in renderer or 'Arc' not in renderer:")
    entry_text = entry_text.replace('未确认NVIDIA渲染器', '未确认Intel Arc渲染器')
    entry_text = entry_text.replace('assert np.array_equal(v,source[\'vertices\'])', "assert v.tobytes()==source['vertices'].tobytes()")
    # 长反馈和真实队列分别建账，避免相互覆盖执行结果。
    for label in ('long', 'live'):
        folder = ROOT/label
        folder.mkdir()
        shutil.copytree(master, folder/'workers')
        shutil.copytree(SOURCE/'inputs', folder/'inputs')
        shutil.copyfile(SOURCE/'manifest.json', folder/'manifest.json')
        entry = folder/'resident_local_batch_feedback.py'
        entry.write_text(entry_text, encoding='utf-8')
        binding = dict(workers={p.name:sha(p) for p in (folder/'workers').iterdir() if p.is_file()},
                       external_libraries=[dict(path=str(import_library), sha256=sha(import_library))],
                       worker_sha256=sha(entry), geometry_policy='report_only_no_distance_stop',
                       source_archive_sha256=sha(ARCHIVE), source_method_sha256=sha(SOURCE/'00-完整长轨迹输入与本机方法冻结.json'))
        (folder/'01-批量方法与依赖绑定.json').write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding='utf-8')
    record = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(), status='completed',
                  planned_long_events=1536, planned_live_events=384, batch_size=5, live_hz=5,
                  source_archive_sha256=sha(ARCHIVE), geogram_import_sha256=sha(import_library),
                  files={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and not any(x in ('memory_build', '__pycache__') for x in p.parts)})
    (ROOT/'00-批更新与本机新质量方法冻结.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='prepared', planned_events=1920), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
