"""链接同次构建的真实Triangle对象，动态库隐藏符号链接失败保持。"""
from pathlib import Path

here=Path(__file__).resolve().parent
text=(here/'104-捕获区域原生重放完整配置实际执行.py').read_text('utf8')
text=text.replace("folder=here/'捕获区域有界细化原生重放完整配置'","folder=here/'捕获区域有界细化原生重放同次对象'")
text=text.replace("root+'/region_replay_03'","root+'/region_replay_04'")
# 实际库未导出Triangle符号，直接链接同一编译已生成的对象，不另换Triangle实现。
text=text.replace("'-lgeogram','-o',remote_folder+'/replay']", "root+'/candidate_build/src/lib/geogram/CMakeFiles/geogram.dir/third_party/triangle/triangle.c.o','-lgeogram','-o',remote_folder+'/replay']")
(here/'106-捕获区域同次Triangle对象实际重放.py').write_text(text,'utf8')
print('同次实际Triangle对象链接入口已保存')
