"""在新版本中修订种子限定分组，保留第九轮已经编译的源码。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here = Path(__file__).resolve().parent
source = here / '第九轮机器精度共面与原平面有界生成'
output = here / '第十轮种子分组与边界一致生成'
output.mkdir()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior_path = here / '147-机器尺度共面与原平面生成源码清单.json'
prior = json.loads(prior_path.read_text('utf8'))
for name, digest in prior['files'].items():
    assert sha(source / name) == digest
    (output / name).write_bytes((source / name).read_bytes())
path = output / 'mesh_surface_intersection_internal.cpp'
code = path.read_text('utf8')
old = '''                        f2 != NO_INDEX && !f_visited_[f2] &&
                        c_is_coplanar_[mesh_.facets.corner(f1,le1)]'''
new = '''                        f2 != NO_INDEX && !f_visited_[f2] &&
                        // 种子限定可能拆分原相邻共面连通域，禁止跨入此前已分配的其他组。
                        (facet_group_[f2]==NO_INDEX || facet_group_[f2]==group_id) &&
                        c_is_coplanar_[mesh_.facets.corner(f1,le1)]'''
assert code.count(old) == 1
code = code.replace(old, new)
old = '''                        f2 == NO_INDEX ||
                        !c_is_coplanar_[mesh_.facets.corner(f1,le)]'''
new = '''                        f2 == NO_INDEX ||
                        // 原相邻共面但被种子判据分到另一组的边，也必须成为当前组边界。
                        facet_group_[f2]!=group_id_ ||
                        !c_is_coplanar_[mesh_.facets.corner(f1,le)]'''
assert code.count(old) == 1
path.write_text(code.replace(old, new), 'utf8')
now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record = {'生成时间': now, '修改时间及修改内容': now + '，首次修订种子组归属和半边边界一致性',
          '文档概述': '只修订分组契约；机器尺度共面及原平面生成是否有效仍须实际输出验证',
          '索引目录': ['files', 'changes'], 'prior_manifest_sha256': sha(prior_path),
          'files': {name: sha(output / name) for name in prior['files']},
          'changes': ['禁止覆盖其他已分配组', '跨组共面边作为当前组边界'],
          'evaluation_status': 'not_started'}
manifest = here / '154-种子分组与边界一致生成源码清单.json'
assert not manifest.exists()
manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', 'utf8')

# 新构建入口只替换版本身份和输出路径，实际配置继续复用原版配对配置。
builder = (here / '148-机器尺度共面原生独立编译.py').read_text('utf8').replace('第九轮', '第十轮')
(here / '155-种子分组与边界一致原生独立编译.py').write_text(builder, 'utf8')
controller = (here / '149-机器尺度共面原生编译上传执行.py').read_text('utf8')
for before, after in [('第九轮', '第十轮'), ('20261006_10', '20261006_11'),
                      ('第九轮机器精度共面与原平面有界生成', '第十轮种子分组与边界一致生成'),
                      ('147-机器尺度共面与原平面生成源码清单.json', '154-种子分组与边界一致生成源码清单.json'),
                      ('148-机器尺度共面原生独立编译.py', '155-种子分组与边界一致原生独立编译.py'),
                      ('150-机器尺度共面实际编译执行记录.json', '157-种子分组与边界一致实际编译执行记录.json'),
                      ('151-机器尺度共面实际编译控制台日志.txt', '158-种子分组与边界一致实际编译控制台日志.txt'),
                      ('152-机器尺度共面实际原生编译记录.json', '159-种子分组与边界一致实际原生编译记录.json')]:
    controller = controller.replace(before, after)
# 版本中文名先替换过轮次，显式绑定实际新源码目录。
controller = controller.replace('第十轮机器精度共面与原平面有界生成', '第十轮种子分组与边界一致生成')
(here / '156-种子分组与边界一致编译上传执行.py').write_text(controller, 'utf8')
print(json.dumps({'status': 'prepared_new_partition_revision', 'files': record['files']}, ensure_ascii=False))
