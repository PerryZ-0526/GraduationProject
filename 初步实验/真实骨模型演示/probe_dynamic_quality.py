"""固定第二步候选，对局部维护参数进行复现实验。"""
import numpy as np
import pymeshlab as pm
from dynamic_quality import DynamicQualityEngine
from real_bone_interactive_app import MillingEngine
from mesh_quality import remesh_local, quality


def main():
    engine = DynamicQualityEngine()
    engine.step()
    MillingEngine.step(engine)
    mesh = engine.current_mesh
    center = np.mean(engine.current_segment, axis=0)
    radius = engine.current_radius + np.linalg.norm(np.diff(engine.current_segment, axis=0))/2+1.2
    for iterations in (3, 5, 8):
        for budget in (.001, .005, .01):
            result, elapsed = remesh_local(mesh, center, iterations=iterations,
                                          radius_mm=radius, surface_budget_mm=budget, precision64=True)
            check = pm.MeshSet()
            check.add_mesh(pm.Mesh(result.vertices, result.faces))
            check.compute_selection_by_self_intersections_per_face()
            print(iterations, budget, check.current_mesh().selected_face_number(),
                  quality(result)['bad_q_pct'], elapsed, flush=True)


if __name__ == '__main__':
    main()
