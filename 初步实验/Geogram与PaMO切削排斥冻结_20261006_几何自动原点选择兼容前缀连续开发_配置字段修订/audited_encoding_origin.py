"""连续入口中的几何原点选择，绑定完整精确检查，不改变物理输入。"""
from pathlib import Path
from geometry_selected_encoding_origin import select_encoding_origin
from automatic_pair_separation import PAIR_CHECKER, PAIR_CHECKER_SHA
from audit_cut_embedding import CHECKER
from audit_followup_candidate import sha256
from locality_masks import save_obj_fp64
from run_geometry_study import execute, save, now
import json


def select_audited_origin(engine, source, original_origin, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    for executable, expected in [(CHECKER, '0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3'),
                                  (PAIR_CHECKER, PAIR_CHECKER_SHA)]:
        if execute(engine.client, ['sha256sum', executable])['stdout'].split()[0] != expected:
            raise ValueError('原点选择精确检查器摘要改变')

    def audit(mesh, index):
        path = output / ('origin_' + str(index) + '.obj')
        save_obj_fp64(mesh, path)
        remote = engine.remote + '/' + output.name + '_origin_' + str(index) + '.obj'
        engine.sftp.put(str(path), remote)
        if execute(engine.client, ['sha256sum', remote])['stdout'].split()[0] != sha256(path):
            raise ValueError('原点选择实际精确输入摘要不符')
        run = execute(engine.client, [CHECKER, remote], timeout=120)
        if run['returncode']:
            raise RuntimeError('完整原点编码精确检查没有成功返回')
        embedding = json.loads(run['stdout'])
        result = {'encoded_sha256': sha256(path), 'embedding': embedding, 'pairs': {}}
        if not embedding['embedded_closed'] and index == 0:
            run = execute(engine.client, [PAIR_CHECKER, remote], timeout=120)
            if run['returncode']:
                raise RuntimeError('默认编码交叠面号检查没有成功返回')
            result['pairs'] = json.loads(run['stdout'])
        return result

    # CPU精确候选选择之后，原入口仍审查实际CUDA与Warp对象，不能省略实际工作源门控。
    result = select_encoding_origin(source, original_origin, audit)
    result.update(生成时间=now(), 修改时间及修改内容='首次生成当前事件原点选择',
                  文档概述='物理源不动，默认失败后生成几何原点候选', 索引目录=['selection', 'attempts'],
                  selector_sha256=sha256(Path(__file__).with_name('geometry_selected_encoding_origin.py')))
    save(output / '01-当前事件原点选择与精确核对.json', result)
    return result
