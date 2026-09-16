"""逐步维护并回灌的动态骨面实验；未通过验收的候选状态不发布。"""
import json
import hashlib
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pymeshlab as pm

import real_bone_demo as R
from mesh_quality import quality, remesh_local, surface_distances, removal_metrics
from real_bone_interactive_app import MillingEngine
from real_bone_system_demo import to_manifold, to_trimesh


class QualityRejected(RuntimeError):
    """候选网格未达到发布门槛，上一已验收状态保持不变。"""


class DynamicQualityEngine(MillingEngine):
    """维护后的骨面直接参与下一步切削，同时保留独立无维护参考序列。"""

    to_manifold = staticmethod(lambda mesh: to_manifold(mesh, precision64=True))
    to_trimesh = staticmethod(lambda mesh: to_trimesh(mesh, precision64=True))

    def reset(self):
        super().reset()
        self.reference = self.to_manifold(self.initial_mesh)
        self.attempts = []
        self.blocked = False

    def export_session(self):
        """随已发布骨面保存全部通过与拒绝记录。"""
        paths = super().export_session()
        # PLY 仅用于预览；NPZ 无损保存已验收双精度坐标及三角索引。
        state_path = Path(paths[0]).with_suffix('.npz')
        np.savez_compressed(state_path, vertices=self.current_mesh.vertices,
                            faces=self.current_mesh.faces)
        audit_path = Path(paths[0]).with_suffix('.quality.json')
        audit_path.write_text(json.dumps(dict(published_steps=self.step_index,
                                             attempts=self.attempts),
                                        ensure_ascii=False, indent=2), encoding='utf8')
        return [*paths, str(state_path), str(audit_path)]

    def step(self):
        if self.blocked:
            raise QualityRejected('上一候选未通过验收，请重置后重试')
        if self.step_index == len(self.trajectory):
            return None
        start = time.perf_counter()
        saved = self.__dict__.copy()
        saved['records'] = list(self.records)
        try:
            row = super().step()
            # 先在双精度内核消除布尔产生的微小边，误差仍与累计参考逐步核验。
            candidate = self.to_trimesh(self.bone.simplify(.001))
            reference = self.reference - self.to_manifold(self.current_tool)
            reference_mesh = self.to_trimesh(reference)
            p0, p1 = self.current_segment
            center = (p0 + p1) / 2
            radius = self.current_radius + np.linalg.norm(p1-p0)/2 + 1.2
            result, maintain_ms = remesh_local(candidate, center, radius_mm=radius,
                                               iterations=3, surface_budget_mm=.005, precision64=True, smooth=False)
            check_start = time.perf_counter()
            retry_ms = 0.
            method = 'local_remesh'
            q = quality(result)
            roi = np.linalg.norm(result.triangles_center-center, axis=1) < radius
            local = result.submesh([np.flatnonzero(roi)], append=True, repair=False)
            local_q = quality(local) if len(local.faces) else q
            check = pm.MeshSet()
            check.add_mesh(pm.Mesh(result.vertices, result.faces))
            check.compute_selection_by_self_intersections_per_face()
            intersections = check.current_mesh().selected_face_number()
            if intersections:
                # 从原候选以更严格投影预算重试，避免在失败结果上继续积累误差。
                result, retry_ms = remesh_local(candidate, center, radius_mm=radius,
                                                iterations=5, surface_budget_mm=.001, precision64=True, smooth=False)
                maintain_ms += retry_ms
                method = 'strict_remesh_retry'
                q = quality(result)
                roi = np.linalg.norm(result.triangles_center-center, axis=1) < radius
                local = result.submesh([np.flatnonzero(roi)], append=True, repair=False)
                local_q = quality(local) if len(local.faces) else q
                check = pm.MeshSet()
                check.add_mesh(pm.Mesh(result.vertices, result.faces))
                check.compute_selection_by_self_intersections_per_face()
                intersections = check.current_mesh().selected_face_number()
            if intersections:
                # 重网格两次均失败时，尝试仅微边简化的候选，仍执行完整门控。
                result = candidate
                method = 'simplify_fallback'
                q = quality(result)
                roi = np.linalg.norm(result.triangles_center-center, axis=1) < radius
                local = result.submesh([np.flatnonzero(roi)], append=True, repair=False)
                local_q = quality(local) if len(local.faces) else q
                check = pm.MeshSet()
                check.add_mesh(pm.Mesh(result.vertices, result.faces))
                check.compute_selection_by_self_intersections_per_face()
                intersections = check.current_mesh().selected_face_number()
            forward = surface_distances(reference_mesh, result, samples=2000)
            backward = surface_distances(result, reference_mesh, samples=2000)
            distance = max(forward['max_mm'], backward['max_mm'])
            accepted = (q['watertight'] and q['winding'] and q['euler']==2 and
                        q['degenerate']==0 and intersections==0 and
                        q['bad_q_pct'] < 1 and local_q['bad_q_pct'] < 5 and distance <= .1)
            audit = dict(step=self.step_index, quality=q, local_bad_pct=local_q['bad_q_pct'],
                         self_intersections=intersections, forward=forward, backward=backward,
                         accepted=bool(accepted), maintain_ms=maintain_ms,
                         method=method,
                         check_ms=(time.perf_counter()-check_start)*1000-retry_ms)
            if not accepted:
                raise QualityRejected(json.dumps(audit, ensure_ascii=False))
            # 只有验收通过才提交维护后的状态；此状态将作为下步布尔运算输入。
            self.bone = self.to_manifold(result)
            self.current_mesh = result
            self.reference = reference
            row.update(removal_metrics(self.initial_volume, self.bone, self.planned_removal))
            row['faces'] = len(result.faces)
            row['removed_mm3'] = self.initial_volume-self.bone.volume()
            row['remaining_area_mm2'], row['overcut_area_mm2'] = self._risk_counts(result)
            row['maintain_ms'] = maintain_ms
            row['check_ms'] = audit['check_ms']
            row['pipeline_ms'] = (time.perf_counter()-start)*1000
            row['quality_bad_pct'] = q['bad_q_pct']
            row['reference_max_mm'] = distance
            row['deadline_missed'] = row['pipeline_ms'] > 100
            audit['pipeline_ms'] = row['pipeline_ms']
            self.attempts.append(audit)
            return row
        except Exception as exc:
            # 回滚工具位置、轨迹进度、网格和计时记录，拒绝发布失败候选。
            attempts = self.attempts
            self.__dict__.update(saved)
            self.attempts = attempts
            self.blocked = True
            self.rejected_mesh = locals().get('result')
            self.attempts.append(dict(step=self.step_index+1, accepted=False,
                                      error=str(exc), pipeline_ms=(time.perf_counter()-start)*1000))
            raise QualityRejected(str(exc)) from exc


def main():
    out = Path(__file__).parent / '逐步质量维护实验'
    out.mkdir(exist_ok=True)
    engine = DynamicQualityEngine()
    for i in range(138):
        try:
            row = engine.step()
            print(i+1, round(row['pipeline_ms'],1), row['quality_bad_pct'],
                  row['reference_max_mm'], flush=True)
        except QualityRejected as exc:
            print('REJECTED', i+1, str(exc), flush=True)
            break
        finally:
            data = dict(time_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                        parameters=dict(precision='float64', pre_simplify_mm=.001,
                                        target_edge_mm=.6, iterations=3, projection_mm=.005,
                                        smooth=False, retry_iterations=5, retry_projection_mm=.001,
                                        global_bad_pct_limit=1, local_bad_pct_limit=5,
                                        sampled_distance_limit_mm=.1, deadline_ms=100,
                                        samples_per_direction=2000, seed=20260907),
                        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        published_steps=engine.step_index, attempts=engine.attempts,
                        rows=engine.records)
            (out/'results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    engine.current_mesh.export(out/'last_accepted.ply')
    np.savez_compressed(out/'last_accepted.npz', vertices=engine.current_mesh.vertices,
                        faces=engine.current_mesh.faces)
    rejected = getattr(engine, 'rejected_mesh', None)
    if rejected is not None:
        np.savez_compressed(out/'rejected_candidate.npz', vertices=rejected.vertices, faces=rejected.faces)
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S')
    (out/f'run_{stamp}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
