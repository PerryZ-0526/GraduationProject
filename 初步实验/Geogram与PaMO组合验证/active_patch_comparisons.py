"""公平对照只替换候选生成及外部契约，保留三个原版工作器和同输入规则。"""
from pathlib import Path
import trimesh
import run_ordered_features as features
from audit_followup_candidate import sha256
from run_active_patch_projection import ActivePatchEngine
from run_active_patch_feedback import audit_active_candidate
from run_constrained_feedback import global_geometry


class ActiveFeatureEngines(features.FeatureEngines):
    def __init__(self,output,port):
        original=features.InitialEncodingEngine
        features.InitialEncodingEngine=ActivePatchEngine
        try:
            super().__init__(output,port)
        finally:
            features.InitialEncodingEngine=original

    def setup(self):
        if (self.output/'01-小特征浅磨工具冻结.json').is_file():
            # 共用小特征setup先核对执行快照；必须在其读取摘要前写入同次入口。
            (self.output/'ordered_features_snapshot.py').write_bytes(self.entry_path.read_bytes())
        info=super().setup()
        names=('active_patch_comparisons.py','run_active_patch_projection.py','run_active_patch_feedback.py')
        paths=[]
        for name in names:
            path=self.output/name;path.write_bytes((Path(__file__).resolve().parent/name).read_bytes());paths.append(path)
        entry=self.output/'active_comparison_entry.py';entry.write_bytes(self.entry_path.read_bytes());paths.append(entry)
        info['actual_active_comparison_sources_sha256']={p.name:sha256(p) for p in paths}
        return info

    def audit(self,*args):
        previous=features.audit_preserved_candidate
        features.audit_preserved_candidate=audit_active_candidate
        try:
            row=super().audit(*args)
        finally:
            features.audit_preserved_candidate=previous
        if row['feature_method']!='boolean' and not row['execution']['returncode']:
            source,tool,labels,folder,_=args
            # 原版审计的面积抽样结论保留；共同几何预算另加入全部顶点探针。
            row['baseline_sampled_audit_status']=row['status']
            geometry=global_geometry(trimesh.load(Path(folder)/'candidate.obj',process=False),trimesh.load(source,process=False))
            row['geometry_to_maintenance_source']=geometry
            row['joint_geometry_protocol']='8192_area_samples_and_all_vertices'
            if row['status']=='accepted_sampled' and geometry['probe_max_mm']>.1:
                row['status']='all_vertex_geometry_budget_rejected'
        return row
