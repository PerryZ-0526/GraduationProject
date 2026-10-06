"""不可变事件记录、小型检查点和可核查的追加索引。"""
from datetime import datetime, timedelta, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.writing')
    with temporary.open('xb') as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    # Windows读者短暂占用目标文件时重试；失败保留完整临时文件供恢复核查。
    for attempt in range(20):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.1)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def file_identity(path):
    return {'path': str(Path(path).resolve()), 'sha256': digest(path)}


def require_file(identity):
    path = Path(identity['path'])
    if digest(path) != identity['sha256']:
        raise ValueError('检查点文件摘要变化：' + str(path))
    return path


def process_alive(pid):
    if os.name == 'nt':
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            if ctypes.windll.kernel32.GetLastError() == 5:
                raise PermissionError('不能确认原进程是否终止')
            return False
        try:
            code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise OSError('不能读取原进程状态')
            return code.value == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class EventStore:
    """一次提交包含参照及全部分支，检查点可由索引最后一条重建。"""
    def __init__(self, folder, binding, resume=False):
        self.folder = Path(folder).resolve()
        if resume:
            if read_json(self.folder / '01-运行绑定.json')['binding'] != binding:
                raise ValueError('方法、输入或运行计划变化，禁止接续旧父链')
        else:
            self.folder.mkdir(parents=True, exist_ok=False)
            (self.folder / 'events').mkdir()
            (self.folder / 'attempts').mkdir()
            atomic_json(self.folder / '01-运行绑定.json', {'time_beijing': now(), 'binding': binding})
        self.lock = self.folder / '.writer.lock'
        if self.lock.exists():
            owner = read_json(self.lock)
            if process_alive(owner['pid']):
                raise RuntimeError('本批写入进程仍活动，禁止并发接续')
            self.lock.rename(self.folder / ('.writer.stale.' + uuid.uuid4().hex))
        with self.lock.open('xb') as stream:
            stream.write(encoded({'pid': os.getpid(), 'time_beijing': now()}))
        self.index = self.folder / '02-事件索引.jsonl'
        self.entries = []
        self.states = {}
        try:
            self._load()
        except BaseException:
            self.close()
            raise

    def _load(self):
        if not self.index.exists():
            return
        previous = '0' * 64
        # 流式核查索引，内存不保留历史详细审计；截断的最后一行单独封存。
        with self.index.open('rb') as stream:
            complete_bytes = 0
            for line in stream:
                if not line.endswith(b'\n'):
                    tail = self.folder / ('02-未提交索引尾部-' + uuid.uuid4().hex + '.bin')
                    tail.write_bytes(line)
                    break
                item = json.loads(line)
                path = self.folder / item['record_file']
                if item['seq'] != len(self.entries) or item['previous'] != previous or digest(path) != item['record_sha256']:
                    raise ValueError('事件索引或记录摘要不一致')
                detail = read_json(path)
                expected = self.states.get(item['route'], {}).get('next_index', 0)
                if detail['event_index'] != expected or detail['state']['next_index'] != expected + 1:
                    raise ValueError('已提交事件前缀不连续')
                self.states[item['route']] = detail['state']
                self.entries.append(item)
                previous = hashlib.sha256(line).hexdigest()
                complete_bytes += len(line)
        if self.index.stat().st_size != complete_bytes:
            # 只恢复没有换行的未提交尾部，完整但错误的行绝不自动修正。
            original = self.folder / ('02-截断前索引-' + uuid.uuid4().hex + '.jsonl')
            self.index.rename(original)
            with original.open('rb') as source, self.index.open('xb') as target:
                remaining = complete_bytes
                while remaining:
                    block = source.read(min(remaining, 1024 * 1024))
                    target.write(block)
                    remaining -= len(block)
                target.flush()
                os.fsync(target.fileno())
        self.previous = previous
        for state in self.states.values():
            for parent in state['parents'].values():
                require_file(parent)
            if state.get('reference'):
                require_file(state['reference']['mesh'])
        atomic_json(self.folder / '03-检查点.json', {'time_beijing': now(), 'committed': len(self.entries), 'states': self.states})

    def pending(self, value):
        payload = {'time_beijing': now(), **value}
        atomic_json(self.folder / '04-当前事件.json', {'payload': payload,
            'payload_sha256': hashlib.sha256(encoded(payload)).hexdigest()})

    def commit(self, route, event, event_index, rows, state, timings, origin=None):
        expected = self.states.get(route, {}).get('next_index', 0)
        if event_index != expected or state['next_index'] != expected + 1:
            raise ValueError('提交事件不是下一条计划事件')
        if [row['branch'] for row in rows] != ['R', *state['parents']]:
            raise ValueError('本事件参照或分支记录不完整')
        number = len(self.entries)
        path = self.folder / 'events' / (f'{number:06d}-' + uuid.uuid4().hex + '.json')
        detail = {'time_beijing': now(), 'route': route, 'event': event, 'event_index': event_index,
                  'rows': rows, 'state': state, 'timings_ms': timings, 'origin': origin}
        atomic_json(path, detail)
        item = {'seq': number, 'route': route, 'event': event, 'record_file': str(path.relative_to(self.folder)),
                'record_sha256': digest(path), 'previous': getattr(self, 'previous', '0' * 64)}
        line = encoded(item)
        with self.index.open('ab') as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
        self.previous = hashlib.sha256(line).hexdigest()
        self.entries.append(item)
        self.states[route] = copy.deepcopy(state)
        atomic_json(self.folder / '03-检查点.json', {'time_beijing': now(), 'committed': len(self.entries), 'states': self.states})
        self.pending({'status': 'committed', 'route': route, 'event': event, 'seq': number})

    def status(self, status, **details):
        atomic_json(self.folder / '05-运行状态.json', {'time_beijing': now(), 'status': status,
            'committed_events': len(self.entries), **details})

    def close(self):
        if self.lock.exists() and read_json(self.lock)['pid'] == os.getpid():
            self.lock.unlink()
