"""核对开发终态冻结源码后执行新参数完整保留评价，禁止改动方法。"""
import json
from pathlib import Path
import sys
from audit_followup_candidate import sha256
from run_constrained_batch import HERE
from run_initial_encoding_feedback import InitialPhysicalEngine
from run_physical_geometry_feedback import main


class FrozenInitialEngine(InitialPhysicalEngine):
    def setup(self):
        # 输入输出参数仍交给原完整控制器；本层只补充冻结绑定。
        prepared=Path(sys.argv[sys.argv.index('--prepared')+1])
        freeze_path=prepared/'03-保留评价方法冻结.json'
        frozen=json.loads(freeze_path.read_text(encoding='utf-8'))
        for item in frozen['current_sources']:
            if sha256(Path(item['source'])) != item['sha256'] or sha256(prepared/item['snapshot']) != item['sha256']:
                raise ValueError('保留评价前方法源码变化：'+item['source'])
        info=super().setup()
        for item in frozen['executed_sources']:
            path=self.output/item['name']
            if path.exists() and sha256(path) != item['sha256']:
                raise ValueError('新执行生成源码与冻结开发方法不同：'+item['name'])
        if info['actual_initial_encoding_worker_sha256'] != frozen['actual_worker_sha256']:
            raise ValueError('实际GPU工作器与冻结版本不同')
        info.update(evaluation_method_freeze_sha256=sha256(freeze_path),
            evaluation_input_manifest_sha256=sha256(prepared/'01-完整范围冻结清单.json'),
            evaluation_scope='同形状家族新参数保留12体48事件，冻结后不调参；非新患者或未见家族')
        return info


if __name__=='__main__':
    main(FrozenInitialEngine)
