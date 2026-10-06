"""只在新私有目录生成已认证双输入的交叉候选版本，原版源码及证据保持。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,shutil,zipfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    base=args.baseline.resolve();root=args.output.resolve();assert root.parent==base.parent and root!=base
    root.mkdir(exist_ok=False);sha=lambda data:hashlib.sha256(data).hexdigest()
    for name in ['opennl.zip','amgcl.zip','libmeshb.zip','rply.zip']:shutil.copyfile(base/name,root/name)
    member='src/lib/geogram/mesh/mesh_surface_intersection.cpp'
    with zipfile.ZipFile(base/'geogram.zip') as old:
        original=old.read(member);text=original.decode()
        before='AABB.compute_facet_bbox_intersections(report_BB);'
        assert text.count(before)==1
        after='''            // 调用方已分别认证两个闭合嵌入输入时，只枚举两个输入之间的候选。
            // 不使用“共享顶点就跳过”规则，跨输入的接触和穿越仍全部送入原精确谓词。
            const bool trusted = CmdLine::arg_is_declared("algo:certified_operands") &&
                CmdLine::get_arg_bool("algo:certified_operands") && has_operand_bits_;
            Attribute<index_t> labels;
            if(trusted) labels.bind_if_is_defined(mesh_.facets.attributes(), "operand_bit");
            index_t counts[4] = {0,0,0,0};bool eligible=trusted && labels.is_bound();
            if(eligible) for(index_t f:mesh_.facets) {
                index_t bit=labels[f];
                if(bit<1 || bit>3) {eligible=false;break;}
                ++counts[bit];
            }
            if(eligible) {
                index_t query_bit=(counts[1]<counts[2]) ? 1 : 2;
                index_t other_bit=(query_bit==1) ? 2 : 1;
                // 标签3的原面同时属于两个已认证输入，与任何原面均共有一个已认证来源。
                for(index_t f:mesh_.facets) if(labels[f]==query_bit) {
                    Box3d box;
                    for(index_t k=0;k<3;++k) {
                        const vec3& a=mesh_.facets.point(f,0);
                        const vec3& b=mesh_.facets.point(f,1);
                        const vec3& c=mesh_.facets.point(f,2);
                        box.xyz_min[k]=std::min(a[k],std::min(b[k],c[k]));
                        box.xyz_max[k]=std::max(a[k],std::max(b[k],c[k]));
                    }
                    AABB.compute_bbox_facet_bbox_intersections(box,[&](index_t g) {
                        if(labels[g]==other_bit) report_BB(std::min(f,g),std::max(f,g));
                    });
                }
            } else {
                // 没有明确认证、来源缺失或不是两个输入时，保留原全量候选路径。
                AABB.compute_facet_bbox_intersections(report_BB);
            }'''
        text=text.replace(before,after)
        text=text.replace('#include <sstream>','#include <geogram/basic/command_line.h>\n#include <sstream>',1)
        changed=text.encode()
        with zipfile.ZipFile(root/'geogram.zip','x',zipfile.ZIP_DEFLATED) as new:
            for info in old.infolist():new.writestr(info,changed if info.filename==member else old.read(info))
    rows=[]
    with zipfile.ZipFile(root/'workers.zip','x',zipfile.ZIP_DEFLATED) as z:
        paths=[q for q in (base/'workers').rglob('*') if q.is_file() and '__pycache__' not in q.parts and
            (q.suffix in ('.py','.cpp') or q.name=='CMakeLists.txt')]
        paths += [q for q in (base/'inputs').rglob('*') if q.is_file()]
        for path in paths:
            name=str(path.relative_to(base));data=path.read_bytes()
            if name=='workers/geogram_memory.cpp':
                text=data.decode();text=text.replace('GEO::CmdLine::set_arg("sys:max_threads", 4);',
                    'GEO::CmdLine::set_arg("sys:max_threads", 4);\n            // 默认不信任输入；调用方明确选择后才启用已认证来源候选。\n            GEO::CmdLine::declare_arg("algo:certified_operands", false, "Certified closed embedded operands");')
                text=text.replace('auto flags = no_simplify ?', 'auto flags = (no_simplify & 1) ?')
                text=text.replace('GEO::mesh_boolean_operation(*result, a, b, "A-B", flags);',
                    '// 既有0/1编码保持旧行为，新位只控制候选枚举，不跳过跨输入精确相交。\n        GEO::CmdLine::set_arg("algo:certified_operands", (no_simplify & 2) ? "true" : "false");\n        GEO::mesh_boolean_operation(*result, a, b, "A-B", flags);');data=text.encode()
            elif name=='workers/geogram_memory.py':
                text=data.decode().replace('no_simplify=False):','no_simplify=False,certified_operands=False):')
                text=text.replace('int(no_simplify))','int(no_simplify)|(2 if certified_operands else 0))')
                text=text.replace("'no_simplify':bool(no_simplify)","'no_simplify':bool(no_simplify),'certified_operands':bool(certified_operands)")
                data=text.encode()
            elif name=='workers/verified_budget_feedback.py':
                text=data.decode().replace("p.add_argument('--fixed-flip-certificate',action='store_true')", 
                    "p.add_argument('--fixed-flip-certificate',action='store_true')\n    p.add_argument('--certified-operand-pairs',action='store_true')")
                text=text.replace('api.difference(v,f,tv,tf,no_simplify=True)',
                    'api.difference(v,f,tv,tf,no_simplify=True,certified_operands=args.certified_operand_pairs)')
                text=text.replace("report['build_identity']=build_identity", "report['build_identity']=build_identity\n    # 本模式仅用于已认证父链及预加载完整认证的工具；无效源仍阻断下一帧。\n    report['certified_operand_pairs']=args.certified_operand_pairs")
                data=text.encode()
            elif name=='inputs/ct_record.json':
                text=json.loads(data)
                for event in text['routes'][0]['events']:
                    event['tool_path']=str(root/'inputs'/Path(event['tool_path']).name)
                text['routes'][0]['events'][0]['parent_path']=str(root/'inputs/initial.obj');data=json.dumps(text,ensure_ascii=False,indent=2).encode()
            z.writestr(name,data);rows.append(dict(name=name,size=len(data),sha256=sha(data)))
        z.writestr('manifest.json',json.dumps(rows,ensure_ascii=False,indent=2))
    record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='prepared_not_validated',
        source_member=member,original_sha256=sha(original),candidate_sha256=sha(changed),
        original_archive_sha256=sha((base/'geogram.zip').read_bytes()),candidate_archive_sha256=sha((root/'geogram.zip').read_bytes()),
        worker_archive_sha256=sha((root/'workers.zip').read_bytes()),
        precondition='每个输入完整闭合嵌入；父链及工具在使用前已认证；缺失来源或多输入退回原候选枚举',
        scope='仅新私有构建；需要原版同输入对照、触碰与穿越控制、保存复审和连续预算验证')
    (root/'01-已认证输入交叉候选源码准备.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
