"""使用构建树实际定位的第三方对象路径，先前路径错误日志保持。"""
from pathlib import Path

here=Path(__file__).resolve().parent
text=(here/'106-捕获区域同次Triangle对象实际重放.py').read_text('utf8')
text=text.replace("folder=here/'捕获区域有界细化原生重放同次对象'","folder=here/'捕获区域有界细化原生重放实际对象'")
text=text.replace("root+'/region_replay_04'","root+'/region_replay_05'")
# 实际对象由geogram_third_party目标生成，路径来自只读构建树核对。
text=text.replace('src/lib/geogram/CMakeFiles/geogram.dir/third_party/triangle/triangle.c.o',
                  'src/lib/geogram/third_party/CMakeFiles/geogram_third_party.dir/triangle/triangle.c.o')
(here/'108-捕获区域实际对象有界细化重放.py').write_text(text,'utf8')
print('实际对象路径已核对并生成独立恢复入口')
