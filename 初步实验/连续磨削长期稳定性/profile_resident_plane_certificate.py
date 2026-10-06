"""在已保存父数组上交错比较精确平面排除与原源认证，不改变原反馈链。"""
from datetime import datetime, timezone, timedelta
import ctypes as C
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter
import numpy as np


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    root, output = map(Path, sys.argv[1:3]); output.mkdir(exist_ok=False)
    workers = root / 'workers'
    ledger = json.loads((root / '02-常驻长序列完整记录.json').read_text())
    assert ledger['status'] == 'completed_with_recorded_failures'
    original = (workers / 'incremental_mesh_memory.cpp').read_text()
    anchor = '        auto callback=[&](const Box* a,const Box* b) {'
    assert original.count(anchor) == 1
    # 输入坐标上的过滤精确方向谓词；严格同侧才排除，零值与共享点继续原检查。
    filter_code = '''        std::int64_t plane_separated=0;
        auto strictly_separated=[&](Mesh::Face_index left,Mesh::Face_index right) {
            const auto* a=f+3*left.idx();const auto* b=f+3*right.idx();
            for(int i=0;i<3;++i) for(int j=0;j<3;++j) if(a[i]==b[j]) return false;
            auto orientation=kernel.orientation_3_object();
            auto one_side=[&](const std::int64_t* plane,const std::int64_t* triangle) {
                PredicateKernel::Point_3 p(v[3*plane[0]],v[3*plane[0]+1],v[3*plane[0]+2]);
                PredicateKernel::Point_3 q(v[3*plane[1]],v[3*plane[1]+1],v[3*plane[1]+2]);
                PredicateKernel::Point_3 r(v[3*plane[2]],v[3*plane[2]+1],v[3*plane[2]+2]);
                auto side=CGAL::COPLANAR;
                for(int k=0;k<3;++k) {
                    const double* point=v+3*triangle[k];
                    auto current=orientation(p,q,r,PredicateKernel::Point_3(point[0],point[1],point[2]));
                    if(current==CGAL::COPLANAR || (k && current!=side)) return false;
                    side=current;
                }
                return true;
            };
            return one_side(a,b) || one_side(b,a);
        };
'''
    projected = '--projected-filter' in sys.argv
    if projected:
        # 任何坐标投影中严格分离都意味着三维不相交；投影方向只影响成本，不参与正确性判定。
        filter_code = '''        std::int64_t plane_separated=0;
        using ProjectedTriangle=std::array<PredicateKernel::Point_2,3>;
        std::vector<std::array<ProjectedTriangle,3>> projections(nf);
        std::vector<std::array<CGAL::Orientation,3>> directions(nf);
        std::vector<int> dominant(nf,2);
        auto orientation=kernel.orientation_2_object();
        for(std::uint64_t i=0;i<nf;++i) {
            const auto* tri=f+3*i;
            double e[3],g[3],normal[3];
            for(int k=0;k<3;++k) {e[k]=v[3*tri[1]+k]-v[3*tri[0]+k];g[k]=v[3*tri[2]+k]-v[3*tri[0]+k];}
            for(int k=0;k<3;++k) normal[k]=std::abs(e[(k+1)%3]*g[(k+2)%3]-e[(k+2)%3]*g[(k+1)%3]);
            dominant[i]=std::max_element(normal,normal+3)-normal;
            for(int axis=0;axis<3;++axis) {
                int x=(axis+1)%3,y=(axis+2)%3;
                auto& points=projections[i][axis];
                for(int j=0;j<3;++j) points[j]=PredicateKernel::Point_2(v[3*tri[j]+x],v[3*tri[j]+y]);
                directions[i][axis]=orientation(points[0],points[1],points[2]);
            }
        }
        auto strictly_separated=[&](Mesh::Face_index left,Mesh::Face_index right) {
            auto i=left.idx(),j=right.idx();const auto* a=f+3*i;const auto* b=f+3*j;
            for(int p=0;p<3;++p) for(int q=0;q<3;++q) if(a[p]==b[q]) return false;
            auto on_projection=[&](int axis) {
                const auto& p=projections[i][axis];const auto& q=projections[j][axis];
                auto outside=[&](const ProjectedTriangle& triangle,const ProjectedTriangle& other,CGAL::Orientation side) {
                    if(side==CGAL::COLLINEAR) return false;
                    for(int edge=0;edge<3;++edge) {
                        bool separated=true;
                        for(int k=0;k<3;++k) {
                            auto sign=orientation(triangle[edge],triangle[(edge+1)%3],other[k]);
                            if(sign==CGAL::COLLINEAR || sign==side) {separated=false;break;}
                        }
                        if(separated) return true;
                    }
                    return false;
                };
                return outside(p,q,directions[i][axis]) || outside(q,p,directions[j][axis]);
            };
            return on_projection(dominant[i]) || (dominant[i]!=dominant[j] && on_projection(dominant[j]));
        };
'''
    candidate = original.replace(anchor, filter_code + anchor)
    before = '            ++checked;\n            if(CGAL::Polygon_mesh_processing::internal::do_faces_intersect<PredicateKernel>('
    assert candidate.count(before) == 1
    candidate = candidate.replace(before, '''            ++checked;
            // 精确严格分离意味着不相交；其余面配对继续作者原完整谓词。
            if(strictly_separated(a->info(),b->info())) {++plane_separated;return;}
            if(CGAL::Polygon_mesh_processing::internal::do_faces_intersect<PredicateKernel>(''')
    before = 'result[8]=std::count(inherited.begin(),inherited.end(),true);result[9]=checked;result[10]=skipped;'
    assert candidate.count(before) == 1
    candidate = candidate.replace(before, before + 'result[11]=plane_separated;')
    wrapper = (workers / 'incremental_mesh_memory.py').read_text()
    before = 'exact_pairs_checked=int(result[9]),unchanged_pairs_inherited=int(result[10]),'
    assert wrapper.count(before) == 1
    wrapper = wrapper.replace(before, before + '\n            strictly_separated_pairs=int(result[11]),')
    libraries = {}; builds = []
    for name, text in [('reference', original), ('candidate', candidate)]:
        folder = output / name; folder.mkdir()
        source = folder / 'incremental_mesh_memory.cpp'; source.write_text(text)
        shutil.copyfile(workers / 'exact_mesh_memory.cpp', folder / 'exact_mesh_memory.cpp')
        module_path = folder / 'incremental_mesh_memory.py'; module_path.write_text(wrapper)
        argv = ['g++', '-std=c++17', '-O3', '-DNDEBUG', '-DCGAL_DISABLE_GMP', '-shared', '-fPIC',
                '-fno-fast-math', '-ffp-contract=off', '-frounding-math', str(source),
                '-o', str(folder / 'libincremental_mesh_memory.so')]
        run = subprocess.run(argv, capture_output=True, text=True)
        (folder / '01-编译日志.txt').write_text(run.stdout + run.stderr)
        builds.append(dict(variant=name, argv=argv, returncode=run.returncode, source_sha256=sha(source)))
        if run.returncode: raise RuntimeError('精确平面候选独立编译失败')
        spec = importlib.util.spec_from_file_location('profile_' + name, module_path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        libraries[name] = module.VerifiedMesh
        print(json.dumps(dict(stage='compiled', variant=name, time_beijing=now())), flush=True)
    rows = []; assets = []
    # 含早期、晚期和真实非法源；每项父数组由保存输出完整认证，绝不拼接不同方法链。
    selections = {'slab': [1, 69, 93, 94], 'sphere': [1, 49, 99, 149, 189, 209, 210]}
    for run in ledger['runs']:
        if run['reference']: continue
        body = 'slab' if 'slab' in run['route'] else 'sphere'; source_folder = Path(run['output'])
        for step in selections[body]:
            parent_path = source_folder / f'e{step-1:03d}_output.npz'
            source_path = source_folder / f'e{step:03d}_source.npz'
            with np.load(parent_path) as data: pv, pf = data['vertices'].copy(), data['faces'].copy()
            with np.load(source_path) as data: v, f = data['vertices'].copy(), data['faces'].copy()
            asset_folder = output / f'{body}_{step+1:03d}'; asset_folder.mkdir()
            for path in [parent_path, source_path]: shutil.copyfile(path, asset_folder / path.name)
            certificates = {name: factory() for name, factory in libraries.items()}
            try:
                roots = {name: cert.check(pv, pf, advance=True) for name, cert in certificates.items()}
                assert all(check['embedded_closed'] for check in roots.values())
                full_result = np.zeros(8, dtype=np.int64); full_ms = np.zeros(4)
                va = np.ascontiguousarray(v, dtype=np.float64); fa = np.ascontiguousarray(f, dtype=np.int64)
                function = certificates['reference'].lib.audit_arrays
                function.argtypes = [C.c_void_p, C.c_uint64, C.c_void_p, C.c_uint64, C.c_void_p, C.c_void_p]
                function.restype = C.c_int
                code = function(va.ctypes.data, len(va), fa.ctypes.data, len(fa), full_result.ctypes.data, full_ms.ctypes.data)
                assert code == 0
                for repeat in range(3):
                    pair = {}
                    for name in (['reference', 'candidate'] if repeat % 2 == 0 else ['candidate', 'reference']):
                        # 核查后不推进，三轮都使用同一完整认证的原父对象。
                        pair[name] = certificates[name].check(v, f, advance=False)
                    keys = ['topology_valid', 'closed', 'embedded_closed', 'self_intersection_pairs',
                            'exact_degenerate_faces', 'inherited_faces', 'exact_pairs_checked']
                    assert all(pair['reference'][key] == pair['candidate'][key] for key in keys)
                    assert pair['candidate']['embedded_closed'] == bool(full_result[6])
                    assert pair['candidate']['self_intersection_pairs'] == int(full_result[5] + full_result[7])
                    rows.append(dict(body=body, step=step+1, repeat=repeat, vertices=len(v), faces=len(f), comparisons=pair))
                assets.append(dict(body=body, step=step+1, parent_sha256=sha(parent_path), source_sha256=sha(source_path),
                    parent_path=str(parent_path), source_path=str(source_path), full_result=full_result.tolist(), full_ms=full_ms.tolist()))
                print(json.dumps(dict(stage='paired', body=body, step=step+1, original=pair['reference']['total_elapsed_ms'],
                    candidate=pair['candidate']['total_elapsed_ms'], separated=pair['candidate']['strictly_separated_pairs'],
                    checked=pair['candidate']['exact_pairs_checked'], full=full_result.tolist(), time_beijing=now())), flush=True)
            finally:
                for cert in certificates.values(): cert.close()
    report = dict(time_beijing=now(), status='completed', source_run=str(root), scope='已见开发数组组件，非法源仍拒绝；不代表完整实时帧或新患者',
        filter_kind='exact_projected_separation' if projected else 'exact_plane_separation',
        frozen_source_sha256=sha(workers/'incremental_mesh_memory.cpp'), worker_sha256=sha(__file__), builds=builds, assets=assets, pairs=rows,
        gpu_environment=subprocess.run(['nvidia-smi'],capture_output=True,text=True).stdout)
    (output / '02-精确平面排除同源组件对照.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(dict(status='completed', pairs=len(rows), time_beijing=now())), flush=True)


if __name__ == '__main__': main()
