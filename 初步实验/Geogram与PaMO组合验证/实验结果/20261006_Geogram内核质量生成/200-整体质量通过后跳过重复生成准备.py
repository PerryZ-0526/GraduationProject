"""质量已通过时跳过全网格第二次三角化，保持原局部与整体质量判据。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十二轮一致二分共边条带生成'
output=here/'第十三轮整体通过后免重复生成';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior_path=here/'185-一致二分共边条带生成源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection.cpp';code=path.read_text('utf8')
old='''        bool rebuilt_shared_neighbors=false;
        if(!shared_splits.empty() && allow_boundary_generation) {'''
new='''        // 共边同步后先查完整候选；已经满足原整体质量判据时不重复全网格准确CDT。
        NativeQualityScore baseline_score=native_quality_score(mesh_,reference);
        long double summation_tolerance=128.0L*std::numeric_limits<double>::epsilon()*baseline_score.total_area;
        auto quality_is_acceptable=[&](const NativeQualityScore& candidate) {
            return candidate.finite && candidate.zero<=baseline_score.zero &&
                candidate.bad<=baseline_score.bad && candidate.area<=baseline_score.area+summation_tolerance;
        };
        vector<index_t> preliminary_cells;
        for(index_t f:mesh_.facets) if(!remove_f[f]) for(index_t k=0;k<3;++k) preliminary_cells.push_back(mesh_.facets.vertex(f,k));
        NativeQualityScore candidate_score=native_quality_score(mesh_,preliminary_cells);
        bool rebuilt_shared_neighbors=false;
        if(!shared_splits.empty() && allow_boundary_generation && !quality_is_acceptable(candidate_score)) {'''
assert code.count(old)==1;code=code.replace(old,new)
old='''        vector<index_t> proposed_cells;
        for(index_t f:mesh_.facets) if(!remove_f[f]) for(index_t k=0;k<3;++k) proposed_cells.push_back(mesh_.facets.vertex(f,k));
        NativeQualityScore baseline_score=native_quality_score(mesh_,reference);
        NativeQualityScore candidate_score=native_quality_score(mesh_,proposed_cells);
        // 浮点求和容差仅按机器精度和本次总面积计算，不设置物理误差门槛。
        long double summation_tolerance=128.0L*std::numeric_limits<double>::epsilon()*baseline_score.total_area;
        bool accept=candidate_score.finite && candidate_score.zero<=baseline_score.zero &&
            candidate_score.bad<=baseline_score.bad && candidate_score.area<=baseline_score.area+summation_tolerance;'''
new='''        // 只有确实执行邻域再生成时才重算候选，参照坐标和判据保持不变。
        if(rebuilt_shared_neighbors) {
            vector<index_t> proposed_cells;
            for(index_t f:mesh_.facets) if(!remove_f[f]) for(index_t k=0;k<3;++k) proposed_cells.push_back(mesh_.facets.vertex(f,k));
            candidate_score=native_quality_score(mesh_,proposed_cells);
        }
        // 浮点求和容差仅按机器精度和本次总面积计算，不设置物理误差门槛。
        bool accept=quality_is_acceptable(candidate_score);'''
assert code.count(old)==1;path.write_text(code.replace(old,new),'utf8')
path=output/'mesh_surface_intersection_internal.cpp';code=path.read_text('utf8')
old='''                if(std::getenv("GEO_NATIVE_QUALITY_TRACE")!=nullptr) {
                    Logger::out("QualityStrip") << "group=" << group_id_ << " slices=" << slices
                        << " before_bad=" << before.bad << " after_bad=" << generated.bad << std::endl;
                }
'''
assert code.count(old)==1
# 条带身份由冻结源码与输出绑定，移除跨日志锁的额外并行打印以避免污染既有JSON轨迹。
path.write_text(code.replace(old,'                // 条带生成不追加另一日志流，避免并行打印交错污染区域JSON轨迹。\n'),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'201-整体通过后免重复生成源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，首次跳过已合格的全网格重复生成',
 '文档概述':'生成与质量判据不变；正式速度与保存质量待同输入验证',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['共边同步完整候选先核对原质量判据','通过则跳过全网格邻域CDT','失败仍执行原再生成与回退','避免并行日志流交错']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'186-一致二分共边条带原生独立编译.py').read_text('utf8').replace('第十二轮','第十三轮')
(here/'202-整体通过后免重复生成原生独立编译.py').write_text(builder,'utf8')
controller=(here/'187-一致二分共边条带编译上传执行.py').read_text('utf8')
for a,b in [('20261006_13','20261006_14'),('第十二轮一致二分共边条带生成',output.name),
 ('185-一致二分共边条带生成源码清单.json',manifest.name),
 ('186-一致二分共边条带原生独立编译.py','202-整体通过后免重复生成原生独立编译.py'),
 ('188-一致二分共边实际编译执行记录.json','204-免重复生成实际编译执行记录.json'),
 ('189-一致二分共边实际编译控制台日志.txt','205-免重复生成实际编译控制台日志.txt'),
 ('190-一致二分共边实际原生编译记录.json','206-免重复生成实际原生编译记录.json'),
 ('第十二轮','第十三轮')]:controller=controller.replace(a,b)
(here/'203-整体通过后免重复生成编译上传执行.py').write_text(controller,'utf8')
print('prepared_same_quality_gate_without_unnecessary_second_generation')
