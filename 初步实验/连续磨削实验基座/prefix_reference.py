"""复用已核查独立参照，每事件最多进行一次原工具布尔。"""
import copy
import hashlib
from pathlib import Path
from time import perf_counter
from event_store import encoded, file_identity, require_file


def prefix_hash(previous, event, tool_sha256):
    return hashlib.sha256(encoded({'previous': previous, 'event': event, 'tool_sha256': tool_sha256})).hexdigest()


class PrefixReference:
    def __init__(self, backend, prepared, route, cursor=None):
        self.backend, self.prepared, self.route = backend, Path(prepared), route
        self.cursor = cursor
        self.tools = {tool['event_id']: tool for tool in route['prefix_tools']}

    def advance(self, event_index, event, reuse, folder):
        started = perf_counter()
        initial = self.prepared / 'inputs' / self.route['initial_mesh']
        previous = self.cursor
        if previous and previous['next_index'] != event_index:
            raise ValueError('参照前缀与当前事件不一致')
        if not previous and event_index:
            raise ValueError('缺少已核查参照前缀')
        identity = previous['mesh'] if previous else {'path': str(initial), 'sha256': self.route['initial_mesh_sha256']}
        parent = require_file(identity)
        tool = self.tools[event]
        require_file({'path': str(self.prepared / 'inputs' / tool['mesh']), 'sha256': tool['sha256']})
        chain = prefix_hash(previous['prefix_sha256'] if previous else self.route['initial_mesh_sha256'], event, tool['sha256'])
        if reuse and previous:
            mesh = self.backend.load_mesh(parent)
            record = {'accepted': True, 'status': 'contained_reused_guarded_reference',
                      'output_sha256': identity['sha256'], 'boolean_count': 0}
            mesh_identity = identity
        else:
            # 原核函数只接收已核查独立父参照和一个原工具，绝不接收质量分支父网格。
            one = copy.deepcopy(self.route)
            one.update(initial_mesh=str(parent.resolve()), initial_mesh_sha256=identity['sha256'], prefix_tools=[tool])
            mesh, record = self.backend.reference_step(self.prepared, one, event, Path(folder))
            record['boolean_count'] = len(record.get('runs', []))
            if mesh is None:
                return None, record, None
            mesh_identity = file_identity(Path(folder) / 'validated_reference.obj')
        record.update(independence='原初态及原工具前缀；不借用任一质量分支父网格',
            original_initial_sha256=self.route['initial_mesh_sha256'], parent_reference=identity,
            prefix_sha256=chain, consumed_event_index=event_index,
            reference_wall_ms=(perf_counter() - started) * 1000)
        self.cursor = {'mesh': mesh_identity, 'next_index': event_index + 1, 'prefix_sha256': chain}
        return mesh, record, self.cursor
