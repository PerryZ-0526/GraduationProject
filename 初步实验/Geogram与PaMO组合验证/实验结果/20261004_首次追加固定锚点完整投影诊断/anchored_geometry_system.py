"""同步首次追加固定点与原FP64几何分支，完整接触能量和CCD保留。"""
import json
from pathlib import Path
import numpy as np
import warp as wp
from preserved_geometry_system import CollisionProtectedSystem as PreservedSystem
from fixed_anchor_contract import promote_fixed_mask


class CollisionProtectedSystem(PreservedSystem):
    def bind_fixed_geometry(self, source, mesh):
        super().bind_fixed_geometry(source, mesh)
        self.anchor_updates = []
        self.initial_anchor_count = int(self.original_fixed_host.sum())
        self.write_anchor_record()

    def write_anchor_record(self):
        Path(__file__).with_name("anchor_updates.json").write_text(json.dumps(dict(
            initial_anchor_count=self.initial_anchor_count, current_anchor_count=int(self.original_fixed_host.sum()),
            updates=self.anchor_updates, scope="首次求导追加固定且坐标逐位不动；实际原FP64毫米坐标保持，非距离下限"),
            ensure_ascii=False, indent=2), encoding="utf-8")

    def set_fixed(self, fixed):
        if hasattr(self, "original_fixed_host"):
            positions = wp.to_torch(self.q)[:self.n_particles].detach().cpu().numpy()
            encoded = self.original_fixed_encoded.detach().cpu().numpy()
            mask, added = promote_fixed_mask(self.original_fixed_host, fixed, positions, encoded, self.diff_calls)
            if len(added):
                # 绑定时保存了所有初态点的FP64几何，只扩展不动点掩码，不修改坐标或接触列表。
                self.original_fixed_host = mask
                self.original_fixed_mask = wp.array(mask.astype(np.int32), dtype=int, device=self.device)
                self.anchor_updates.append(dict(diff_call=self.diff_calls, added_vertices=added.tolist(),
                    encoded_initial_exact=True))
                self.write_anchor_record()
        super().set_fixed(fixed)
